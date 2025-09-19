"""
OCR Processing Endpoint
"""

import logging
import uuid
import base64
import time
from typing import Optional, Union
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from fastapi.responses import JSONResponse

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
from src.services.processing_orchestrator import (
    ProcessingOrchestrator,
    ProcessingConfig
)
from src.services.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for async jobs (use Redis/DB in production)
async_jobs = {}


@router.post("/api/v1/ocr", response_model=Union[OCRResponseFull, OCRResponseMinimal, OCRResponseOCROnly, AsyncJobResponse])
async def process_ocr(
    background_tasks: BackgroundTasks,
    request: OCRRequest = Body(...)
):
    """
    Comprehensive OCR processing endpoint

    This endpoint provides flexible OCR processing with optional quality checks,
    enhancement, and configurable response formats.

    Args:
        request: OCR processing request with source, options, and thresholds

    Returns:
        Response based on return_format and async settings
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
                "request": request
            }

            # Schedule background processing
            background_tasks.add_task(
                process_document_async,
                job_id=job_id,
                document_id=document_id,
                request=request
            )

            return AsyncJobResponse(
                status="accepted",
                job_id=job_id,
                message="Document submitted for processing",
                estimated_time_seconds=30 if request.processing_options.enable_enhancement else 10
            )

        # Synchronous processing
        result = await process_document_sync(document_id, request)
        return result

    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_document_sync(document_id: str, request: OCRRequest):
    """
    Process document synchronously

    Args:
        document_id: Unique document identifier
        request: OCR processing request

    Returns:
        Formatted response based on return_format
    """
    start_time = time.time()

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

        # Create processing config from request
        config = ProcessingConfig(
            quality_threshold=request.thresholds.image_quality_threshold,
            confidence_threshold=request.thresholds.confidence_threshold,
            enable_enhancements=["context"] if request.processing_options.enable_enhancement else []
        )

        # Initialize orchestrator with modular options
        orchestrator = ProcessingOrchestrator(config)

        # Process document with options
        # Quality check is always performed - it acts as a gate for OCR
        if request.source.type == SourceType.FILE:
            result = orchestrator.process_document(
                document_data=file_data,
                config_override=config,
                skip_quality_check=False,  # Always perform quality check
                skip_ocr=not request.processing_options.enable_ocr,
                skip_enhancement=not request.processing_options.enable_enhancement
            )
        else:
            result = orchestrator.process_document(
                document_url=obs_url,
                config_override=config,
                skip_quality_check=False,  # Always perform quality check
                skip_ocr=not request.processing_options.enable_ocr,
                skip_enhancement=not request.processing_options.enable_enhancement
            )

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Build response based on format
        response_builder = ResponseBuilder()

        if request.processing_options.return_format == ReturnFormat.MINIMAL:
            return response_builder.build_minimal(
                document_id=document_id,
                result=result,
                processing_time_ms=processing_time_ms
            )
        elif request.processing_options.return_format == ReturnFormat.OCR_ONLY:
            return response_builder.build_ocr_only(
                document_id=document_id,
                result=result,
                processing_time_ms=processing_time_ms
            )
        else:  # FULL
            return response_builder.build_full(
                document_id=document_id,
                result=result,
                request=request,
                processing_time_ms=processing_time_ms
            )

    except Exception as e:
        logger.error(f"Document processing failed: {e}")

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


async def process_document_async(job_id: str, document_id: str, request: OCRRequest):
    """
    Process document asynchronously (background task)

    Args:
        job_id: Async job identifier
        document_id: Document identifier
        request: OCR processing request
    """
    try:
        # Update job status
        async_jobs[job_id]["status"] = "processing"

        # Process document
        result = await process_document_sync(document_id, request)

        # Store result
        async_jobs[job_id]["status"] = "completed"
        async_jobs[job_id]["result"] = result.dict()

    except Exception as e:
        logger.error(f"Async processing failed for job {job_id}: {e}")
        async_jobs[job_id]["status"] = "failed"
        async_jobs[job_id]["error"] = str(e)


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