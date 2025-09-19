"""
Document processing endpoints
"""

import logging
import uuid
import asyncio
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from src.services.processing_orchestrator import (
    ProcessingOrchestrator,
    ProcessingConfig
)
from src.models.document import Document, ProcessingStatus
from src.models.api_models import ProcessingResult

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for demo (use database in production)
processing_results = {}
processing_documents = {}


@router.post("/process", response_model=dict)
async def process_document(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    obs_url: Optional[str] = Form(None),
    quality_threshold: float = Form(30.0),
    confidence_threshold: float = Form(80.0),
    enable_grammar: bool = Form(False),
    enable_context: bool = Form(False),
    enable_structure: bool = Form(False),
    enable_all: bool = Form(False)
):
    """
    Process a document through the OCR pipeline

    Args:
        file: Document file to upload (optional if obs_url provided)
        obs_url: OBS URL to document (optional if file provided)
        quality_threshold: Minimum quality score to proceed (default: 30)
        confidence_threshold: Minimum confidence for automatic processing (default: 80)
        enable_grammar: Enable grammar enhancement
        enable_context: Enable context analysis
        enable_structure: Enable structure analysis
        enable_all: Enable all enhancements

    Returns:
        Processing ID and initial status
    """
    try:
        # Validate input
        if not file and not obs_url:
            raise HTTPException(
                status_code=400,
                detail="Either file upload or OBS URL must be provided"
            )

        # Generate unique document ID
        document_id = str(uuid.uuid4())

        # Determine enhancements
        enhancements = []
        if enable_all:
            enhancements = ["grammar", "context", "structure"]
        else:
            if enable_grammar:
                enhancements.append("grammar")
            if enable_context:
                enhancements.append("context")
            if enable_structure:
                enhancements.append("structure")

        # Create processing config
        config = ProcessingConfig(
            quality_threshold=quality_threshold,
            confidence_threshold=confidence_threshold,
            enable_enhancements=enhancements
        )

        # Create document record
        if file:
            # Get file extension from filename
            filename = file.filename
            file_ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
            # Map content type to format
            content_format = file.content_type.split('/')[-1].lower() if file.content_type else file_ext
            if content_format == 'jpeg':
                content_format = 'jpg'

            # Read file content for size
            file_content = await file.read()

            document = Document(
                id=document_id,
                filename=filename,
                format=content_format if content_format in ['pdf', 'jpg', 'jpeg', 'png', 'tiff'] else file_ext,
                file_path=f"temp/{document_id}",
                size_bytes=len(file_content) if file else 0,
                checksum="0" * 64  # Temporary checksum (64 chars for SHA256), will be calculated properly later
            )
        else:
            # For OBS URL, extract format from filename
            obs_filename = obs_url.split("/")[-1]
            file_ext = obs_filename.split('.')[-1].lower() if '.' in obs_filename else 'jpg'
            if file_ext == 'jpeg':
                file_ext = 'jpg'

            document = Document(
                id=document_id,
                filename=obs_filename,
                format=file_ext if file_ext in ['pdf', 'jpg', 'jpeg', 'png', 'tiff'] else 'jpg',
                file_path=obs_url,
                size_bytes=1024 * 1024,  # Default 1MB for OBS files, actual size will be retrieved later
                checksum="0" * 64  # Temporary checksum (64 chars for SHA256) for OBS files
            )

        # Store document
        processing_documents[document_id] = document

        # Process document in background
        if file:
            # Use the file_content we already read
            background_tasks.add_task(
                process_document_task,
                document_id,
                file_content=file_content,
                config=config
            )
        else:
            background_tasks.add_task(
                process_document_task,
                document_id,
                obs_url=obs_url,
                config=config
            )

        return {
            "document_id": document_id,
            "status": "processing",
            "message": f"Document submitted for processing with {len(enhancements)} enhancements",
            "enhancements": enhancements
        }

    except Exception as e:
        logger.error(f"Error submitting document for processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_document_task(
    document_id: str,
    file_content: Optional[bytes] = None,
    obs_url: Optional[str] = None,
    config: Optional[ProcessingConfig] = None
):
    """
    Background task to process document

    Args:
        document_id: Unique document identifier
        file_content: File bytes if uploaded
        obs_url: OBS URL if provided
        config: Processing configuration
    """
    try:
        logger.info(f"Processing document {document_id}")

        # Update document status
        if document_id in processing_documents:
            processing_documents[document_id].processing_status = ProcessingStatus.PROCESSING

        # Initialize orchestrator
        orchestrator = ProcessingOrchestrator(config)

        # Process document
        if file_content:
            result = orchestrator.process_document(
                document_data=file_content,
                config_override=config
            )
        else:
            result = orchestrator.process_document(
                document_url=obs_url,
                config_override=config
            )

        # Update result with document ID
        result.document_id = document_id

        # Store result
        processing_results[document_id] = result

        # Update document status
        if document_id in processing_documents:
            processing_documents[document_id].processing_status = result.status

        logger.info(f"Document {document_id} processing completed with status: {result.status}")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")

        # Create error result
        error_result = ProcessingResult(
            document_id=document_id,
            status=ProcessingStatus.FAILED,
            error_message=str(e)
        )

        processing_results[document_id] = error_result

        # Update document status
        if document_id in processing_documents:
            processing_documents[document_id].processing_status = ProcessingStatus.FAILED


@router.post("/process/batch", response_model=dict)
async def process_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    quality_threshold: float = Form(30.0),
    confidence_threshold: float = Form(80.0),
    enable_enhancements: List[str] = Form([])
):
    """
    Process multiple documents in batch

    Args:
        files: List of document files
        quality_threshold: Minimum quality score
        confidence_threshold: Minimum confidence for automatic processing
        enable_enhancements: List of enhancements to apply

    Returns:
        List of processing IDs
    """
    try:
        batch_id = str(uuid.uuid4())
        document_ids = []

        for file in files:
            document_id = str(uuid.uuid4())
            document_ids.append(document_id)

            # Create config
            config = ProcessingConfig(
                quality_threshold=quality_threshold,
                confidence_threshold=confidence_threshold,
                enable_enhancements=enable_enhancements
            )

            # Process each file
            file_content = await file.read()
            background_tasks.add_task(
                process_document_task,
                document_id,
                file_content=file_content,
                config=config
            )

        return {
            "batch_id": batch_id,
            "document_ids": document_ids,
            "total_documents": len(document_ids),
            "status": "processing"
        }

    except Exception as e:
        logger.error(f"Error processing batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))