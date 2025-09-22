"""
Preprocessing Endpoints for Document Enhancement
"""

import logging
import uuid
import base64
import tempfile
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, File, UploadFile, Query, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from io import BytesIO

from src.services.image_quality_service import ImageQualityAssessor
from src.services.image_preprocessing_service import ImagePreprocessor
from src.services.format_detector import FormatDetector
from src.services.obs_service import OBSService
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
quality_assessor = ImageQualityAssessor()
preprocessor = ImagePreprocessor()
format_detector = FormatDetector()


class PreprocessRequest(BaseModel):
    """Request model for preprocessing"""
    source_type: str  # "file" or "obs_url"
    file_data: Optional[str] = None  # Base64 encoded file
    obs_url: Optional[str] = None  # OBS URL
    quality_threshold: float = 80.0  # Only preprocess if quality below this
    save_to_obs: bool = False  # Save preprocessed file to OBS


class PreprocessResponse(BaseModel):
    """Response model for preprocessing"""
    status: str
    format_detected: str
    quality_score: float
    preprocessed: bool
    preprocessed_url: Optional[str] = None  # If saved to OBS
    preprocessed_data: Optional[str] = None  # Base64 if not saved to OBS
    message: Optional[str] = None


@router.post("/api/v1/preprocess", response_model=PreprocessResponse)
async def preprocess_document(request: PreprocessRequest = Body(...)):
    """
    Preprocess a document to improve OCR quality.

    Supports all 11 formats: PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, PCX, ICO, PSD, PDF

    Args:
        request: Preprocessing request with source and options

    Returns:
        Preprocessed document data or URL
    """
    try:
        # Get file data
        if request.source_type == "file" and request.file_data:
            file_bytes = base64.b64decode(request.file_data)
        elif request.source_type == "obs_url" and request.obs_url:
            obs_service = OBSService()
            # Download from OBS
            parts = request.obs_url[6:].split('/', 1) if request.obs_url.startswith('obs://') else request.obs_url.split('/', 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid OBS URL: {request.obs_url}")
            _, object_key = parts
            file_bytes = obs_service.download_file(object_key)
        else:
            raise ValueError("Invalid source configuration")

        # Detect format
        format_detected = format_detector.detect_format(file_bytes)
        if not format_detected:
            raise ValueError("Unable to detect file format")

        logger.info(f"Format detected: {format_detected}")

        # Assess quality
        assessment = quality_assessor.assess(image_data=file_bytes)
        quality_score = assessment.overall_score

        logger.info(f"Quality score: {quality_score:.1f}")

        # Determine if preprocessing is needed
        needs_preprocessing = quality_score < request.quality_threshold

        if needs_preprocessing:
            logger.info(f"Preprocessing needed (score {quality_score:.1f} < threshold {request.quality_threshold})")
            # Apply preprocessing
            preprocessed_bytes = preprocessor.preprocess(
                file_bytes,
                assessment,
                enable_preprocessing=True
            )

            # If preprocessing changed the file
            if preprocessed_bytes != file_bytes:
                preprocessed = True
                message = f"Document preprocessed successfully (quality: {quality_score:.1f})"
            else:
                preprocessed = False
                preprocessed_bytes = file_bytes
                message = f"Document quality acceptable, no preprocessing applied"
        else:
            preprocessed = False
            preprocessed_bytes = file_bytes
            message = f"Document quality good ({quality_score:.1f}), no preprocessing needed"

        # Handle output
        if request.save_to_obs:
            # Save to OBS
            obs_service = OBSService()
            object_key = f"preprocessed/{uuid.uuid4().hex[:12]}.{format_detected.lower()}"
            obs_service.upload_file(preprocessed_bytes, object_key)
            preprocessed_url = f"obs://{settings.obs_bucket}/{object_key}"
            preprocessed_data = None
            logger.info(f"Saved preprocessed document to OBS: {preprocessed_url}")
        else:
            # Return as base64
            preprocessed_url = None
            preprocessed_data = base64.b64encode(preprocessed_bytes).decode('utf-8')

        return PreprocessResponse(
            status="success",
            format_detected=format_detected,
            quality_score=quality_score,
            preprocessed=preprocessed,
            preprocessed_url=preprocessed_url,
            preprocessed_data=preprocessed_data,
            message=message
        )

    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/preprocess/upload")
async def preprocess_upload(
    file: UploadFile = File(...),
    quality_threshold: float = Query(80.0, description="Quality threshold for preprocessing"),
    save_to_obs: bool = Query(False, description="Save to OBS instead of returning data")
):
    """
    Preprocess an uploaded file.

    Args:
        file: File to preprocess
        quality_threshold: Only preprocess if quality below this
        save_to_obs: Save to OBS instead of returning file

    Returns:
        Preprocessed file for download or OBS URL
    """
    try:
        # Read file
        file_bytes = await file.read()

        # Detect format
        format_detected = format_detector.detect_format(file_bytes)
        if not format_detected:
            raise ValueError("Unable to detect file format")

        logger.info(f"Uploaded file format: {format_detected}")

        # Assess quality
        assessment = quality_assessor.assess(image_data=file_bytes)
        quality_score = assessment.overall_score

        logger.info(f"Quality score: {quality_score:.1f}")

        # Apply preprocessing if needed
        if quality_score < quality_threshold:
            logger.info(f"Preprocessing file (score {quality_score:.1f} < {quality_threshold})")
            preprocessed_bytes = preprocessor.preprocess(
                file_bytes,
                assessment,
                enable_preprocessing=True
            )
            preprocessed = True
            filename = f"preprocessed_{file.filename}"
        else:
            preprocessed_bytes = file_bytes
            preprocessed = False
            filename = file.filename
            logger.info(f"Quality acceptable ({quality_score:.1f}), no preprocessing needed")

        if save_to_obs:
            # Save to OBS and return URL
            obs_service = OBSService()
            object_key = f"preprocessed/{uuid.uuid4().hex[:12]}_{filename}"
            obs_service.upload_file(preprocessed_bytes, object_key)
            obs_url = f"obs://{settings.obs_bucket}/{object_key}"

            return JSONResponse({
                "status": "success",
                "format_detected": format_detected,
                "quality_score": quality_score,
                "preprocessed": preprocessed,
                "obs_url": obs_url,
                "message": f"File saved to OBS: {obs_url}"
            })
        else:
            # Return file for download
            media_type = {
                "PDF": "application/pdf",
                "PNG": "image/png",
                "JPG": "image/jpeg",
                "JPEG": "image/jpeg",
                "BMP": "image/bmp",
                "GIF": "image/gif",
                "TIFF": "image/tiff",
                "WEBP": "image/webp",
                "PCX": "image/x-pcx",
                "ICO": "image/x-icon",
                "PSD": "application/x-photoshop"
            }.get(format_detected.upper(), "application/octet-stream")

            return StreamingResponse(
                BytesIO(preprocessed_bytes),
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Quality-Score": str(quality_score),
                    "X-Preprocessed": str(preprocessed)
                }
            )

    except Exception as e:
        logger.error(f"Preprocessing upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/preprocess/download/{document_id}")
async def download_preprocessed(
    document_id: str,
    from_obs: bool = Query(False, description="Download from OBS")
):
    """
    Download a previously preprocessed document.

    Args:
        document_id: Document identifier or OBS key
        from_obs: Whether to download from OBS

    Returns:
        Preprocessed document file
    """
    try:
        if from_obs:
            # Download from OBS
            obs_service = OBSService()
            file_bytes = obs_service.download_file(f"preprocessed/{document_id}")

            # Try to detect format from file bytes
            format_detected = format_detector.detect_format(file_bytes)

            media_type = {
                "PDF": "application/pdf",
                "PNG": "image/png",
                "JPG": "image/jpeg",
                "JPEG": "image/jpeg"
            }.get(format_detected, "application/octet-stream")

            return StreamingResponse(
                BytesIO(file_bytes),
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename=preprocessed_{document_id}"
                }
            )
        else:
            # For local storage, we'd need to implement a storage mechanism
            # For now, return an error
            raise HTTPException(
                status_code=501,
                detail="Local storage not implemented. Use OBS storage instead."
            )

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=404, detail=f"Document not found: {str(e)}")