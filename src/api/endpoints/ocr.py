"""
OCR Processing Endpoint with Extended Format Support
"""

import logging
import uuid
import base64
import time
from typing import Optional, Union, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body, File, UploadFile, Query
from pydantic import BaseModel

from src.models.ocr_api import (
    OCRRequest,
    OCRResponseFull,
    OCRResponseMinimal,
    OCRResponseOCROnly,
    AsyncJobResponse,
    JobStatusResponse,
    ReturnFormat,
    SourceType
)
from src.models.errors import ErrorCode, get_http_status_for_error
from src.services.processing_orchestrator import (
    ProcessingOrchestrator,
    ProcessingConfig
)
from src.services.response_builder import ResponseBuilder
from src.services.format_detector import FormatDetector
# from src.services.format_adapter import FormatAdapterService  # No longer needed - direct OCR
from src.services.pdf_processor import PDFProcessor
from src.services.history_service import HistoryService
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for async jobs (use Redis/DB in production)
async_jobs = {}

# Initialize services
format_detector = FormatDetector()
# format_adapter = FormatAdapterService()  # No longer needed - direct OCR
pdf_processor = PDFProcessor()
history_service = HistoryService()


class FormatSupportedResponse(BaseModel):
    """Response for format validation"""
    format_detected: str
    is_supported: bool
    validation_errors: Optional[list[str]] = None
    capabilities: Optional[Dict[str, Any]] = None


@router.post("/api/v1/ocr", response_model=Union[OCRResponseFull, OCRResponseMinimal, OCRResponseOCROnly, AsyncJobResponse])
async def process_ocr(
    background_tasks: BackgroundTasks,
    request: OCRRequest = Body(...),
    page_number: Optional[int] = Query(None, description="Specific page number for PDF processing"),
    process_all_pages: bool = Query(False, description="Process all pages for multi-page documents"),
    auto_rotation: bool = Query(True, description="Apply automatic rotation detection"),
    format_validation: bool = Query(True, description="Validate file format before processing"),
    preprocessing_quality_threshold: Optional[float] = Query(None, description="Override quality threshold for preprocessing (default: 80.0)")
):
    """
    Comprehensive OCR processing endpoint with extended format support

    Supports 11 file formats: PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, ICO, PSD, PDF, PCX

    Preprocessing:
    - Automatically applied when enable_preprocessing=true in processing_options
    - Uses quality threshold to determine if preprocessing is needed
    - Improves OCR accuracy for low-quality images

    For PDF files:
    - By default, only the first page is processed
    - Use page_number parameter to process a specific page
    - Use process_all_pages=true to process all pages (makes separate API calls per page)

    Args:
        request: OCR processing request with source, options, and thresholds
        page_number: Optional specific page for PDF processing (1-indexed)
        process_all_pages: Process all PDF pages (may take longer)
        auto_rotation: Apply automatic text rotation detection
        format_validation: Validate format constraints before processing
        preprocessing_quality_threshold: Override quality threshold for preprocessing

    Returns:
        Response based on return_format and async settings

    Error Codes:
        - 415 Unsupported Media Type: Format not supported
        - 413 Payload Too Large: File exceeds size limit
        - 400 Bad Request: Invalid dimensions or format validation failed
    """
    try:
        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"

        # If async processing requested
        if request.async_processing:
            if not background_tasks:
                raise HTTPException(
                    status_code=400,
                    detail="Async processing not available"
                )

            # Create job
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            async_jobs[job_id] = {
                "status": "pending",
                "document_id": document_id,
                "request": request,
                "page_number": page_number,
                "process_all_pages": process_all_pages,
                "auto_rotation": auto_rotation
            }

            # Schedule background processing
            background_tasks.add_task(
                process_document_async,
                job_id=job_id,
                document_id=document_id,
                request=request,
                page_number=page_number,
                process_all_pages=process_all_pages,
                auto_rotation=auto_rotation,
                format_validation=format_validation,
                preprocessing_quality_threshold=preprocessing_quality_threshold
            )

            return AsyncJobResponse(
                status="accepted",
                job_id=job_id,
                message="Document submitted for processing",
                estimated_time_seconds=60 if process_all_pages else (30 if request.processing_options.enable_enhancement else 10)
            )

        # Synchronous processing
        result = await process_document_sync(
            document_id,
            request,
            page_number=page_number,
            process_all_pages=process_all_pages,
            auto_rotation=auto_rotation,
            format_validation=format_validation,
            preprocessing_quality_threshold=preprocessing_quality_threshold
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_document_sync(
    document_id: str,
    request: OCRRequest,
    page_number: Optional[int] = None,
    process_all_pages: bool = False,
    auto_rotation: bool = True,
    format_validation: bool = True,
    preprocessing_quality_threshold: Optional[float] = None
):
    """
    Process document synchronously with format support

    Args:
        document_id: Unique document identifier
        request: OCR processing request
        page_number: Optional page number for PDF
        process_all_pages: Process all PDF pages
        auto_rotation: Apply rotation detection
        format_validation: Validate format before processing

    Returns:
        Formatted response based on return_format
    """
    start_time = time.time()
    format_detected = None

    try:
        # Prepare input data
        if request.source.type == SourceType.FILE:
            # Decode base64 file
            try:
                file_data = base64.b64decode(request.source.file)
            except Exception as e:
                raise ValueError(f"Invalid base64 file data: {e}")
        else:
            # OBS URL
            file_data = None
            obs_url = request.source.obs_url

        # Detect and validate format
        if request.source.type == SourceType.FILE:
            format_detected = format_detector.detect_format(file_data)

            if not format_detected:
                raise HTTPException(
                    status_code=415,
                    detail={
                        "error_code": ErrorCode.FORMAT_NOT_SUPPORTED.value,
                        "message": "Could not detect file format"
                    }
                )

            # Check if format is supported
            if format_detected not in settings.supported_formats:
                raise HTTPException(
                    status_code=415,
                    detail={
                        "error_code": ErrorCode.FORMAT_NOT_SUPPORTED.value,
                        "message": f"Format {format_detected} is not supported",
                        "supported_formats": settings.supported_formats
                    }
                )

            # Validate format constraints if requested
            if format_validation:
                from src.core.validators.format_validator import FormatValidator
                validator = FormatValidator()
                is_valid, error_code = validator.validate_file(file_data, format_detected)

                if not is_valid:
                    http_status = get_http_status_for_error(error_code)
                    raise HTTPException(
                        status_code=http_status,
                        detail={
                            "error_code": error_code.value,
                            "message": f"Format validation failed: {error_code.value}",
                            "format_detected": format_detected
                        }
                    )

        # Handle PDF specially
        if format_detected == "PDF":
            result = await process_pdf_document(
                document_id=document_id,
                file_data=file_data,
                page_number=page_number,
                process_all_pages=process_all_pages,
                request=request,
                preprocessing_quality_threshold=preprocessing_quality_threshold
            )
        else:
            # Process other formats
            result = await process_image_document(
                document_id=document_id,
                file_data=file_data,
                format_detected=format_detected,
                auto_rotation=auto_rotation,
                request=request,
                preprocessing_quality_threshold=preprocessing_quality_threshold
            )

        # Format information is tracked separately for logging
        logger.info(f"Format detected: {format_detected}")

        # Store in history
        try:
            history_service.add_processing_record(
                document_id=document_id,
                format_detected=format_detected,
                status="success",
                text_extracted=getattr(result, 'extracted_text', None) or getattr(result, 'raw_text', None),
                confidence=getattr(result, 'confidence_score', None) or getattr(result, 'ocr_confidence', None),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document processing failed: {e}")

        # Store failure in history
        try:
            history_service.add_processing_record(
                document_id=document_id,
                format_detected=format_detected,
                status="failed",
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        except:
            pass

        # Return error response based on format
        if request.processing_options.return_format == ReturnFormat.MINIMAL:
            return OCRResponseMinimal(
                status="failed",
                extracted_text="",
                routing_decision="requires_review",
                confidence_score=0.0,
                document_id=document_id,
                error=str(e)
            )
        elif request.processing_options.return_format == ReturnFormat.OCR_ONLY:
            return OCRResponseOCROnly(
                status="failed",
                raw_text="",
                word_count=0,
                ocr_confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                document_id=document_id,
                error=str(e)
            )
        else:
            # For full format, let the error propagate
            raise


async def process_pdf_document(
    document_id: str,
    file_data: bytes,
    page_number: Optional[int],
    process_all_pages: bool,
    request: OCRRequest,
    preprocessing_quality_threshold: Optional[float] = None
) -> Any:
    """
    Process PDF document - Huawei OCR processes entire PDF natively
    """
    start_time = time.time()

    # Create processing config from request
    # Use override threshold if provided
    quality_threshold = preprocessing_quality_threshold or request.thresholds.image_quality_threshold

    config = ProcessingConfig(
        quality_threshold=quality_threshold,
        confidence_threshold=request.thresholds.confidence_threshold,
        enable_enhancements=["context"] if request.processing_options.enable_enhancement else [],
        enable_preprocessing=request.processing_options.enable_preprocessing
    )

    # Initialize orchestrator
    orchestrator = ProcessingOrchestrator(config)

    # Process PDF with orchestrator (Huawei OCR handles complete PDF)
    result = orchestrator.process_document(
        document_data=file_data,
        config_override=config,
        skip_quality_check=False,
        skip_ocr=not request.processing_options.enable_ocr,
        skip_enhancement=not request.processing_options.enable_enhancement
    )

    # Set document_id
    result.document_id = document_id

    # Add PDF-specific metadata to processing metrics
    if hasattr(result, 'processing_metrics') and result.processing_metrics:
        result.processing_metrics["format"] = "PDF"
        if page_number:
            result.processing_metrics["page_requested"] = page_number
            result.processing_metrics["note"] = f"Huawei OCR processes entire PDF. Page {page_number} requested."
        elif process_all_pages:
            result.processing_metrics["note"] = "Huawei OCR processes entire PDF natively."
        else:
            result.processing_metrics["note"] = "Huawei OCR processes entire PDF. Use page_number=N to specify page interest."

    # Calculate processing time
    processing_time_ms = (time.time() - start_time) * 1000

    # Build response based on format
    response_builder = ResponseBuilder()

    if request.processing_options.return_format == ReturnFormat.MINIMAL:
        return response_builder.build_minimal(document_id, result, processing_time_ms)
    elif request.processing_options.return_format == ReturnFormat.OCR_ONLY:
        return response_builder.build_ocr_only(document_id, result, processing_time_ms)
    else:
        return response_builder.build_full(document_id, result, request, processing_time_ms)


async def process_image_document(
    document_id: str,
    file_data: bytes,
    format_detected: str,
    auto_rotation: bool,
    request: OCRRequest,
    preprocessing_quality_threshold: Optional[float] = None
) -> Any:
    """Process image format documents"""
    start_time = time.time()

    # Direct processing - no conversion needed (Huawei OCR handles all formats)
    # Just pass the file data directly
    metadata = {
        "format": format_detected,
        "auto_rotation": auto_rotation,
        "size_bytes": len(file_data)
    }

    # Create processing config from request
    # Use override threshold if provided
    quality_threshold = preprocessing_quality_threshold or request.thresholds.image_quality_threshold

    config = ProcessingConfig(
        quality_threshold=quality_threshold,
        confidence_threshold=request.thresholds.confidence_threshold,
        enable_enhancements=["context"] if request.processing_options.enable_enhancement else [],
        enable_preprocessing=request.processing_options.enable_preprocessing
    )

    # Initialize orchestrator
    orchestrator = ProcessingOrchestrator(config)

    # Process with orchestrator directly using original file data
    result = orchestrator.process_document(
        document_data=file_data,
        config_override=config,
        skip_quality_check=False,
        skip_ocr=not request.processing_options.enable_ocr,
        skip_enhancement=not request.processing_options.enable_enhancement
    )

    # Set document_id
    result.document_id = document_id

    # Add format metadata to result if not already there
    if hasattr(result, 'processing_metrics') and result.processing_metrics:
        result.processing_metrics["format_metadata"] = metadata

    # Calculate processing time
    processing_time_ms = (time.time() - start_time) * 1000

    # Build response based on format
    response_builder = ResponseBuilder()

    if request.processing_options.return_format == ReturnFormat.MINIMAL:
        return response_builder.build_minimal(document_id, result, processing_time_ms)
    elif request.processing_options.return_format == ReturnFormat.OCR_ONLY:
        return response_builder.build_ocr_only(document_id, result, processing_time_ms)
    else:
        return response_builder.build_full(document_id, result, request, processing_time_ms)


async def process_document_async(
    job_id: str,
    document_id: str,
    request: OCRRequest,
    page_number: Optional[int] = None,
    process_all_pages: bool = False,
    auto_rotation: bool = True,
    format_validation: bool = True,
    preprocessing_quality_threshold: Optional[float] = None
):
    """
    Process document asynchronously (background task)

    Args:
        job_id: Async job identifier
        document_id: Document identifier
        request: OCR processing request
        page_number: Optional page number for PDF
        process_all_pages: Process all PDF pages
        auto_rotation: Apply rotation detection
        format_validation: Validate format before processing
    """
    try:
        # Update job status
        async_jobs[job_id]["status"] = "processing"

        # Process document
        result = await process_document_sync(
            document_id,
            request,
            page_number=page_number,
            process_all_pages=process_all_pages,
            auto_rotation=auto_rotation,
            format_validation=format_validation,
            preprocessing_quality_threshold=preprocessing_quality_threshold
        )

        # Store result
        async_jobs[job_id]["status"] = "completed"
        # Use model_dump instead of deprecated dict()
        async_jobs[job_id]["result"] = result.model_dump() if hasattr(result, 'model_dump') else result

    except Exception as e:
        logger.error(f"Async processing failed for job {job_id}: {e}")
        async_jobs[job_id]["status"] = "failed"
        async_jobs[job_id]["error"] = str(e)


@router.post("/api/v1/ocr/validate-format", response_model=FormatSupportedResponse)
async def validate_format(
    file: UploadFile = File(...),
    expected_format: Optional[str] = Query(None, description="Expected format to validate against")
):
    """
    Validate file format and get capabilities

    Args:
        file: File to validate
        expected_format: Optional expected format

    Returns:
        Format validation result with capabilities
    """
    try:
        file_data = await file.read()

        # Detect format
        detected_format = format_detector.detect_format(file_data)

        if not detected_format:
            return FormatSupportedResponse(
                format_detected="unknown",
                is_supported=False,
                validation_errors=["Could not detect file format"]
            )

        # Check if supported
        is_supported = detected_format in settings.supported_formats

        # Validate against expected if provided
        validation_errors = []
        if expected_format and detected_format.upper() != expected_format.upper():
            # Handle JPEG/JPG equivalence
            if not (expected_format.upper() in ['JPEG', 'JPG'] and detected_format in ['JPEG', 'JPG']):
                validation_errors.append(f"Expected {expected_format}, detected {detected_format}")

        # Get capabilities
        # All supported formats have the same capabilities with Huawei OCR
        capabilities = {
            "can_extract_text": True,
            "can_extract_tables": True,
            "can_extract_kv_pairs": True,
            "supports_rotation": True,
            "multi_page": detected_format == "PDF"
        } if is_supported else None

        return FormatSupportedResponse(
            format_detected=detected_format,
            is_supported=is_supported,
            validation_errors=validation_errors if validation_errors else None,
            capabilities=capabilities
        )

    except Exception as e:
        logger.error(f"Format validation error: {e}")
        return FormatSupportedResponse(
            format_detected="unknown",
            is_supported=False,
            validation_errors=[str(e)]
        )


@router.get("/api/v1/ocr/supported-formats")
async def get_supported_formats():
    """
    Get list of all supported formats with their capabilities

    Returns:
        Dictionary of supported formats and their capabilities
    """
    formats_info = {}

    for format_name in settings.supported_formats:
        # All formats have the same capabilities with Huawei OCR
        formats_info[format_name] = {
            "can_extract_text": True,
            "can_extract_tables": True,
            "can_extract_kv_pairs": True,
            "supports_rotation": True,
            "multi_page": format_name == "PDF"
        }

    return {
        "supported_formats": settings.supported_formats,
        "total_formats": len(settings.supported_formats),
        "format_details": formats_info
    }


@router.get("/api/v1/ocr/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of async OCR job

    Args:
        job_id: Job identifier

    Returns:
        Job status and result if completed
    """
    if job_id not in async_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = async_jobs[job_id]

    # Calculate progress
    progress = None
    if job["status"] == "processing":
        progress = 50  # Rough estimate
    elif job["status"] == "completed":
        progress = 100

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress_percentage=progress,
        result=job.get("result"),
        error=job.get("error")
    )


@router.delete("/api/v1/ocr/job/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel or delete async job

    Args:
        job_id: Job identifier

    Returns:
        Cancellation status
    """
    if job_id not in async_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # In real implementation, would need to cancel running task
    del async_jobs[job_id]

    return {"status": "cancelled", "job_id": job_id}