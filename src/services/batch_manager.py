"""
Batch processing manager for concurrent document OCR processing
"""

import logging
import uuid
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from threading import Lock
from queue import Queue
from dataclasses import dataclass, field

from src.models.batch import BatchJob, BatchStatus, ProcessingResult, ErrorDetail
from src.services.format_detector import FormatDetector
# from src.services.format_adapter import FormatAdapterService  # No longer needed - direct OCR
from src.services.ocr_service import HuaweiOCRService as OCRService
from src.services.pdf_processor import PDFProcessor
from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProcessingTask:
    """Individual document processing task"""
    task_id: str
    document_id: str
    file_data: bytes
    filename: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    submitted_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchProcessingManager:
    """
    Manages concurrent batch processing of documents
    - Uses ThreadPoolExecutor for parallel processing
    - Maintains FIFO order for fairness
    - Provides individual error isolation
    - Tracks progress for each job
    """

    def __init__(self):
        self.format_detector = FormatDetector()
        self.ocr_service = OCRService()
        self.pdf_processor = PDFProcessor()
        self.max_workers = settings.pdf_parallel_pages  # Default: 4
        self.max_batch_size = settings.max_batch_size  # Default: 20

        # Job tracking
        self._jobs: Dict[str, BatchJob] = {}
        self._jobs_lock = Lock()

        # Task queue for FIFO processing
        self._task_queue: Queue[ProcessingTask] = Queue()

        # Executor management
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: Dict[Future, str] = {}

        logger.info(f"BatchProcessingManager initialized with {self.max_workers} workers")

    def create_batch_job(
        self,
        documents: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> BatchJob:
        """
        Create a new batch processing job

        Args:
            documents: List of document data with file_data and optional metadata
            options: Processing options (fail_fast, auto_rotation, etc.)

        Returns:
            BatchJob instance with unique job_id
        """
        if len(documents) > self.max_batch_size:
            raise ValueError(f"Batch size {len(documents)} exceeds limit of {self.max_batch_size}")

        job_id = f"batch_{uuid.uuid4().hex[:12]}"
        options = options or {}

        # Create batch job with documents
        import base64
        from src.models.batch import BatchDocument
        batch_documents = []
        for doc in documents:
            # Encode file data to base64 if needed
            file_data = doc.get("file_data", b"")
            if isinstance(file_data, bytes):
                file_b64 = base64.b64encode(file_data).decode('utf-8')
            else:
                file_b64 = file_data  # Assume already base64

            batch_documents.append(BatchDocument(
                document_id=doc.get("document_id", f"doc_{uuid.uuid4().hex[:12]}"),
                file=file_b64,
                format_hint=doc.get("format_hint"),
                processing_options=doc.get("options")
            ))

        batch_job = BatchJob(
            job_id=job_id,
            documents=batch_documents,
            fail_fast=options.get("fail_fast", False),
            max_workers=min(self.max_workers, len(documents))
        )

        # Create processing tasks
        tasks = []
        for idx, doc in enumerate(documents):
            task = ProcessingTask(
                task_id=f"{job_id}_doc_{idx}",
                document_id=doc.get("document_id", f"doc_{idx}"),
                file_data=doc["file_data"],
                filename=doc.get("filename"),
                options={
                    "auto_rotation": options.get("auto_rotation", True),
                    "enhance_quality": options.get("enhance_quality", False),
                    "page_number": doc.get("page_number"),  # For PDF specific page
                    "process_all_pages": doc.get("process_all_pages", False)
                }
            )
            tasks.append(task)

        # Store job and tasks
        with self._jobs_lock:
            self._jobs[job_id] = batch_job

            # Add tasks to queue (FIFO)
            for task in tasks:
                self._task_queue.put(task)

        logger.info(f"Created batch job {job_id} with {len(documents)} documents")

        return batch_job

    def process_batch(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Process a batch job

        Args:
            job_id: Batch job ID
            progress_callback: Optional callback for progress updates
                              (job_id, completed, total, status)

        Returns:
            Batch processing results
        """
        with self._jobs_lock:
            if job_id not in self._jobs:
                raise ValueError(f"Job {job_id} not found")

            batch_job = self._jobs[job_id]

        if batch_job.status != BatchStatus.PENDING:
            logger.warning(f"Job {job_id} already processed with status {batch_job.status}")
            return batch_job.to_response()

        batch_job.started_at = datetime.now()
        batch_job.status = BatchStatus.PROCESSING

        try:
            # Process with thread pool
            results = self._process_with_executor(
                batch_job,
                progress_callback
            )

            # Update job with results
            for doc_id, result in results.items():
                if "error" in result:
                    batch_job.add_error(doc_id, ErrorDetail(
                        error_code=result.get("error_code", "PROCESSING_ERROR"),
                        error_message=result["error"],
                        details={"timestamp": datetime.now().isoformat()}
                    ))
                else:
                    batch_job.add_result(doc_id, ProcessingResult(
                        document_id=doc_id,
                        status="success",
                        format_detected=result.get("format_detected"),
                        ocr_text=result.get("text", ""),
                        confidence_score=result.get("confidence", 0.0),
                        processing_time_ms=result.get("processing_time_ms", 0),
                        metadata={
                            "ocr_provider": "huawei",
                            "pages_processed": result.get("pages_processed")
                        }
                    ))

            # Determine final status
            batch_job.complete()

        except Exception as e:
            logger.error(f"Batch processing failed for job {job_id}: {e}")
            batch_job.status = BatchStatus.FAILED
            batch_job.completed_at = datetime.now()

        finally:
            # Cleanup
            with self._jobs_lock:
                if batch_job.status == BatchStatus.COMPLETED:
                    # Keep completed jobs for history
                    pass
                elif batch_job.status == BatchStatus.FAILED:
                    # Keep failed jobs for debugging
                    pass

        return batch_job.to_response()

    def _process_with_executor(
        self,
        batch_job: BatchJob,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process documents using ThreadPoolExecutor

        Returns:
            Dictionary mapping document_id to results
        """
        results = {}
        processed_count = 0

        # Get tasks for this job
        tasks = []
        temp_queue = []

        # Extract tasks from queue (we'll put back non-matching ones)
        while not self._task_queue.empty():
            task = self._task_queue.get()
            if task.task_id.startswith(batch_job.job_id):
                tasks.append(task)
            else:
                temp_queue.append(task)

        # Put back non-matching tasks
        for task in temp_queue:
            self._task_queue.put(task)

        # Process with executor
        with ThreadPoolExecutor(max_workers=batch_job.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._process_single_document, task): task
                for task in tasks
            }

            # Process results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]

                try:
                    result = future.result(timeout=60)  # 60 second timeout per document
                    results[task.document_id] = result
                    processed_count += 1

                    # Update progress
                    if progress_callback:
                        progress_callback(
                            batch_job.job_id,
                            processed_count,
                            batch_job.total_documents,
                            "processing"
                        )

                    logger.info(f"Processed document {task.document_id} ({processed_count}/{batch_job.total_documents})")

                    # Check fail_fast
                    if batch_job.fail_fast and "error" in result:
                        logger.warning(f"Fail-fast triggered by error in {task.document_id}")
                        # Cancel remaining futures
                        for f in future_to_task:
                            if f != future and not f.done():
                                f.cancel()
                        break

                except Exception as e:
                    logger.error(f"Document {task.document_id} processing failed: {e}")
                    results[task.document_id] = {
                        "error": str(e),
                        "error_code": "PROCESSING_TIMEOUT" if "timeout" in str(e).lower() else "PROCESSING_ERROR"
                    }
                    processed_count += 1

                    # Check fail_fast
                    if batch_job.fail_fast:
                        logger.warning(f"Fail-fast triggered by exception in {task.document_id}")
                        # Cancel remaining futures
                        for f in future_to_task:
                            if f != future and not f.done():
                                f.cancel()
                        break

        # Final progress update
        if progress_callback:
            progress_callback(
                batch_job.job_id,
                processed_count,
                batch_job.total_documents,
                "completed"
            )

        return results

    def _process_single_document(self, task: ProcessingTask) -> Dict[str, Any]:
        """
        Process a single document

        Args:
            task: Processing task with document data

        Returns:
            Processing result or error
        """
        task.started_at = datetime.now()
        task.status = "processing"

        try:
            # Detect format
            format_name = self.format_detector.detect_format(task.file_data)

            if not format_name:
                return {
                    "error": "Could not detect file format",
                    "error_code": "FORMAT_DETECTION_FAILED"
                }

            logger.debug(f"Processing {task.document_id} as {format_name}")

            # Handle PDF specially
            if format_name == "PDF":
                result = self._process_pdf_document(task)
            else:
                result = self._process_image_document(task, format_name)

            # Add common metadata
            result["format_detected"] = format_name
            result["document_id"] = task.document_id

            if task.filename:
                result["filename"] = task.filename

            # Calculate processing time
            task.completed_at = datetime.now()
            processing_time = (task.completed_at - task.started_at).total_seconds() * 1000
            result["processing_time_ms"] = int(processing_time)

            task.status = "completed"
            task.result = result

            return result

        except Exception as e:
            logger.error(f"Error processing document {task.document_id}: {e}")
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()

            return {
                "error": str(e),
                "error_code": "PROCESSING_ERROR",
                "document_id": task.document_id
            }

    def _process_pdf_document(self, task: ProcessingTask) -> Dict[str, Any]:
        """
        Process PDF document with page handling
        """
        options = task.options

        # Check if specific page requested
        if options.get("page_number"):
            page_result = self.pdf_processor.process_pdf_page(
                pdf_bytes=task.file_data,
                page_number=options["page_number"]
            )

            if page_result["status"] == "success":
                return {
                    "text": page_result["text"],
                    "confidence": page_result.get("confidence", 0.0),
                    "pages_processed": 1,
                    "page_number": options["page_number"]
                }
            else:
                return {
                    "error": page_result.get("error", "PDF page processing failed"),
                    "error_code": "PDF_PAGE_ERROR"
                }

        # Process all pages
        elif options.get("process_all_pages", False):
            # Use parallel processing for multi-page PDFs
            result = self.pdf_processor.process_all_pages_parallel(
                pdf_bytes=task.file_data,
                max_workers=2  # Limited parallelism for PDFs
            )

            if result["status"] in ["success", "partial_success"]:
                # Aggregate text from all pages
                combined_text = result.get("combined_text", "")
                avg_confidence = result.get("average_confidence", 0.0)

                return {
                    "text": combined_text,
                    "confidence": avg_confidence,
                    "pages_processed": result.get("successful_pages", 0),
                    "total_pages": result.get("total_pages", 0),
                    "failed_pages": result.get("failed_pages", []),
                    "partial_success": result["status"] == "partial_success"
                }
            else:
                return {
                    "error": result.get("error", "PDF processing failed"),
                    "error_code": "PDF_PROCESSING_ERROR"
                }

        # Default: process first page only
        else:
            page_result = self.pdf_processor.process_pdf_page(
                pdf_bytes=task.file_data,
                page_number=1
            )

            if page_result["status"] == "success":
                return {
                    "text": page_result["text"],
                    "confidence": page_result.get("confidence", 0.0),
                    "pages_processed": 1,
                    "page_number": 1,
                    "note": "Only first page processed. Use process_all_pages=true for full document."
                }
            else:
                return {
                    "error": page_result.get("error", "PDF processing failed"),
                    "error_code": "PDF_ERROR"
                }

    def _process_image_document(self, task: ProcessingTask, format_name: str) -> Dict[str, Any]:
        """
        Process image document
        """
        try:
            # Direct processing - no conversion needed
            # Huawei OCR handles all formats natively
            # Just use the file data directly
            file_data = task.file_data

            # Apply options
            if task.options.get("auto_rotation", True):
                # Auto-rotation is handled in the converter
                pass

            # Save image temporarily and process with OCR
            import tempfile
            import os
            from pathlib import Path

            # Determine file extension based on format
            ext_map = {
                'PNG': '.png', 'JPG': '.jpg', 'JPEG': '.jpg',
                'BMP': '.bmp', 'GIF': '.gif', 'TIFF': '.tiff',
                'WebP': '.webp', 'PCX': '.pcx', 'ICO': '.ico',
                'PSD': '.psd', 'PDF': '.pdf'
            }
            extension = ext_map.get(format_name.upper(), '.png')

            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
                tmp_file.write(file_data)
                tmp_path = tmp_file.name

            try:
                ocr_response = self.ocr_service.process_document(image_path=Path(tmp_path))

                if not ocr_response.error_code:
                    # Extract text from OCR response
                    extracted_text = ""
                    if ocr_response.result:
                        for item in ocr_response.result:
                            if item.ocr_result and item.ocr_result.words_block_list:
                                for word_block in item.ocr_result.words_block_list:
                                    if word_block.words:
                                        extracted_text += word_block.words + " "

                    ocr_result = {
                        "status": "success",
                        "text": extracted_text.strip(),
                        "confidence": 85.0  # Default confidence for now
                    }
                else:
                    ocr_result = {
                        "status": "failed",
                        "error": ocr_response.error_msg or "OCR processing failed"
                    }
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if ocr_result.get("status") == "success":
                return {
                    "text": ocr_result.get("text", ""),
                    "confidence": ocr_result.get("confidence", 0.0)
                }
            else:
                return {
                    "error": ocr_result.get("error", "OCR processing failed"),
                    "error_code": "OCR_ERROR"
                }

        except ImportError:
            # FormatAdapterService not yet implemented
            logger.warning("FormatAdapterService not available, using basic processing")

            # Fallback to basic OCR service
            # Save file data temporarily
            import tempfile
            import os
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=f'.{format_name.lower()}', delete=False) as tmp_file:
                tmp_file.write(task.file_data)
                tmp_path = tmp_file.name

            try:
                ocr_response = self.ocr_service.process_document(image_path=Path(tmp_path))

                if not ocr_response.error_code:
                    # Extract text from OCR response
                    extracted_text = ""
                    if ocr_response.result:
                        for item in ocr_response.result:
                            if item.ocr_result and item.ocr_result.words_block_list:
                                for word_block in item.ocr_result.words_block_list:
                                    if word_block.words:
                                        extracted_text += word_block.words + " "

                    ocr_result = {
                        "status": "success",
                        "text": extracted_text.strip(),
                        "confidence": 85.0  # Default confidence for now
                    }
                else:
                    ocr_result = {
                        "status": "failed",
                        "error": ocr_response.error_msg or "OCR processing failed"
                    }
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if ocr_result.get("status") == "success":
                return {
                    "text": ocr_result.get("text", ""),
                    "confidence": ocr_result.get("confidence", 0.0)
                }
            else:
                return {
                    "error": ocr_result.get("error", "OCR processing failed"),
                    "error_code": "OCR_ERROR"
                }

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get current status of a batch job

        Args:
            job_id: Batch job ID

        Returns:
            Job status and results
        """
        with self._jobs_lock:
            if job_id not in self._jobs:
                return {
                    "error": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }

            batch_job = self._jobs[job_id]
            return batch_job.to_response()

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running batch job

        Args:
            job_id: Batch job ID

        Returns:
            True if cancelled, False otherwise
        """
        with self._jobs_lock:
            if job_id not in self._jobs:
                return False

            batch_job = self._jobs[job_id]

            if batch_job.status in [BatchStatus.COMPLETED, BatchStatus.FAILED]:
                return False  # Already finished

            batch_job.status = BatchStatus.CANCELLED
            batch_job.completed_at = datetime.now()

            # TODO: Cancel running futures if using persistent executor

            logger.info(f"Cancelled batch job {job_id}")
            return True

    def cleanup_old_jobs(self, retention_hours: int = 24):
        """
        Clean up old completed/failed jobs

        Args:
            retention_hours: Hours to retain completed jobs
        """
        cutoff_time = datetime.now().timestamp() - (retention_hours * 3600)

        with self._jobs_lock:
            jobs_to_remove = []

            for job_id, job in self._jobs.items():
                if job.completed_at and job.completed_at.timestamp() < cutoff_time:
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self._jobs[job_id]
                logger.debug(f"Cleaned up old job {job_id}")

            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue and processing status

        Returns:
            Queue statistics
        """
        with self._jobs_lock:
            pending_jobs = sum(1 for j in self._jobs.values() if j.status == BatchStatus.PENDING)
            processing_jobs = sum(1 for j in self._jobs.values() if j.status == BatchStatus.PROCESSING)
            completed_jobs = sum(1 for j in self._jobs.values() if j.status == BatchStatus.COMPLETED)
            failed_jobs = sum(1 for j in self._jobs.values() if j.status == BatchStatus.FAILED)

        return {
            "queue_size": self._task_queue.qsize(),
            "pending_jobs": pending_jobs,
            "processing_jobs": processing_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "max_workers": self.max_workers,
            "max_batch_size": self.max_batch_size
        }