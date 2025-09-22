"""
Batch processing endpoint for multiple document OCR
"""

import logging
import base64
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.services.batch_manager import BatchProcessingManager
from src.services.history_service import HistoryService
from src.models.batch import BatchStatus
from src.models.errors import ErrorCode
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
batch_manager = BatchProcessingManager()
history_service = HistoryService()


class BatchDocument(BaseModel):
    """Single document in batch request"""
    document_id: str = Field(..., description="Unique identifier for this document")
    file_data: str = Field(..., description="Base64 encoded file data")
    filename: Optional[str] = Field(None, description="Original filename")
    page_number: Optional[int] = Field(None, description="Specific page for PDF processing")
    process_all_pages: bool = Field(False, description="Process all pages for PDF")


class BatchProcessingRequest(BaseModel):
    """Batch processing request"""
    documents: List[BatchDocument] = Field(..., min_items=1, max_items=20)
    fail_fast: bool = Field(False, description="Stop on first error")
    auto_rotation: bool = Field(True, description="Apply automatic rotation detection")
    enhance_quality: bool = Field(False, description="Apply quality enhancement")
    timeout_per_document: int = Field(60, description="Timeout in seconds per document")


class BatchProcessingResponse(BaseModel):
    """Batch processing response with multi-status"""
    job_id: str
    status: str
    total_documents: int
    successful_documents: int
    failed_documents: int
    results: Dict[str, Any]
    errors: Dict[str, Any]
    processing_time_ms: Optional[int] = None


class DocumentResult(BaseModel):
    """Result for a single document"""
    document_id: str
    status: str
    text: Optional[str] = None
    confidence: Optional[float] = None
    format_detected: Optional[str] = None
    pages_processed: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    processing_time_ms: Optional[int] = None


@router.post("/api/v1/batch", status_code=207)  # 207 Multi-Status
async def process_batch(
    request: BatchProcessingRequest = Body(...),
    parallel_workers: Optional[int] = Query(None, ge=1, le=10, description="Number of parallel workers")
):
    """
    Process multiple documents in batch

    Processes up to 20 documents concurrently with individual error isolation.
    Returns 207 Multi-Status with per-document results.

    Args:
        request: Batch processing request with documents and options
        parallel_workers: Override default parallel workers (default: 4)

    Returns:
        Multi-status response with individual document results

    Error Handling:
        - Individual document errors don't fail the entire batch (unless fail_fast=true)
        - Each document result includes its own status and error information
        - HTTP 207 indicates mixed success/failure results
    """
    try:
        # Validate batch size
        if len(request.documents) > settings.max_batch_size:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size {len(request.documents)} exceeds maximum of {settings.max_batch_size}"
            )

        # Prepare documents for processing
        documents = []
        for doc in request.documents:
            try:
                # Decode base64 data
                file_data = base64.b64decode(doc.file_data)

                documents.append({
                    "document_id": doc.document_id,
                    "file_data": file_data,
                    "filename": doc.filename,
                    "page_number": doc.page_number,
                    "process_all_pages": doc.process_all_pages
                })
            except Exception as e:
                logger.error(f"Failed to decode document {doc.document_id}: {e}")

                if request.fail_fast:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to decode document {doc.document_id}: {e}"
                    )

                # Add to failed documents
                documents.append({
                    "document_id": doc.document_id,
                    "file_data": b"",  # Empty data will fail in processing
                    "error": f"Failed to decode base64: {e}"
                })

        # Create batch job
        options = {
            "fail_fast": request.fail_fast,
            "auto_rotation": request.auto_rotation,
            "enhance_quality": request.enhance_quality,
            "timeout_per_document": request.timeout_per_document
        }

        if parallel_workers:
            options["max_workers"] = min(parallel_workers, 10)

        batch_job = batch_manager.create_batch_job(documents, options)

        # Process batch synchronously (could be made async with job tracking)
        result = batch_manager.process_batch(
            job_id=batch_job.job_id,
            progress_callback=lambda job_id, completed, total, status:
                logger.info(f"Batch {job_id}: {completed}/{total} - {status}")
        )

        # Store batch result in history
        try:
            history_service.add_batch_record(
                job_id=batch_job.job_id,
                total_documents=result["total_documents"],
                successful_documents=result["successful_documents"],
                failed_documents=result["failed_documents"],
                status=result["status"],
                started_at=batch_job.started_at,
                completed_at=batch_job.completed_at,
                results=result.get("document_results"),
                errors=result.get("document_errors")
            )
        except Exception as e:
            logger.warning(f"Failed to save batch history: {e}")

        # Prepare response
        response = BatchProcessingResponse(
            job_id=result["job_id"],
            status=result["status"],
            total_documents=result["total_documents"],
            successful_documents=result["successful_documents"],
            failed_documents=result["failed_documents"],
            results=result.get("document_results", {}),
            errors=result.get("document_errors", {}),
            processing_time_ms=result.get("processing_time_ms")
        )

        return Response(
            content=response.json(),
            status_code=207,  # Multi-Status
            media_type="application/json"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/batch/{job_id}")
async def get_batch_status(job_id: str):
    """
    Get status of batch processing job

    Args:
        job_id: Batch job identifier

    Returns:
        Batch job status and results
    """
    try:
        # Get job status from batch manager
        job_status = batch_manager.get_job_status(job_id)

        if "error" in job_status and job_status["error"] == "Job not found":
            # Try to get from history
            history = history_service.get_batch_history(job_id)

            if history:
                return {
                    "job_id": job_id,
                    "status": history["status"],
                    "total_documents": history["total_documents"],
                    "successful_documents": history["successful_documents"],
                    "failed_documents": history["failed_documents"],
                    "results": history.get("results", {}),
                    "errors": history.get("errors", {}),
                    "created_at": history["created_at"],
                    "from_history": True
                }
            else:
                raise HTTPException(status_code=404, detail=f"Batch job {job_id} not found")

        return job_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/batch/{job_id}/cancel")
async def cancel_batch_job(job_id: str):
    """
    Cancel a running batch job

    Args:
        job_id: Batch job identifier

    Returns:
        Cancellation status
    """
    try:
        success = batch_manager.cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job {job_id} - job not found or already completed"
            )

        return {
            "status": "cancelled",
            "job_id": job_id,
            "message": "Batch job cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel batch job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/batch/queue/status")
async def get_queue_status():
    """
    Get current batch processing queue status

    Returns:
        Queue statistics and current processing status
    """
    try:
        queue_status = batch_manager.get_queue_status()

        return {
            "queue_status": queue_status,
            "max_batch_size": settings.max_batch_size,
            "default_parallel_workers": settings.pdf_parallel_pages
        }

    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/batch/validate")
async def validate_batch(
    request: BatchProcessingRequest = Body(...)
):
    """
    Validate batch request without processing

    Checks document formats and validates constraints.

    Args:
        request: Batch processing request to validate

    Returns:
        Validation results for each document
    """
    from src.services.format_detector import FormatDetector
    from src.core.validators.format_validator import FormatValidator

    format_detector = FormatDetector()
    format_validator = FormatValidator()

    validation_results = []

    for doc in request.documents:
        result = {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "valid": False,
            "format_detected": None,
            "errors": []
        }

        try:
            # Decode base64
            file_data = base64.b64decode(doc.file_data)

            # Detect format
            format_detected = format_detector.detect_format(file_data)
            result["format_detected"] = format_detected

            if not format_detected:
                result["errors"].append("Could not detect file format")
            elif format_detected not in settings.supported_formats:
                result["errors"].append(f"Format {format_detected} is not supported")
            else:
                # Validate constraints
                is_valid, error_code = format_validator.validate_file(file_data, format_detected)

                if is_valid:
                    result["valid"] = True
                else:
                    result["errors"].append(f"Validation failed: {error_code.value}")

        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")

        validation_results.append(result)

    # Calculate summary
    valid_count = sum(1 for r in validation_results if r["valid"])

    return {
        "total_documents": len(request.documents),
        "valid_documents": valid_count,
        "invalid_documents": len(request.documents) - valid_count,
        "validation_results": validation_results
    }