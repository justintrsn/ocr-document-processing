"""
Health and configuration endpoints
"""

import logging
from fastapi import APIRouter
from datetime import datetime

from src.core.config import settings
# EnhancementType removed - using single COMPLETE mode only

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=dict)
async def health_check():
    """
    Health check endpoint

    Returns:
        Service health status
    """
    try:
        # Basic health check
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.app_env,
            "services": {
                "api": "operational",
                "ocr": "operational",  # Could add actual OCR service check
                "llm": "operational",  # Could add actual LLM service check
                "storage": "operational"
            }
        }

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/config/enhancement-options", response_model=dict)
async def get_enhancement_options():
    """
    Get available LLM enhancement options

    Returns:
        Available enhancement types and descriptions
    """
    return {
        "available_enhancements": [
            {
                "type": "grammar",
                "name": "Grammar & Spelling",
                "description": "Correct grammar and spelling errors in extracted text",
                "estimated_time_seconds": 25,
                "enabled_by_default": False
            },
            {
                "type": "context",
                "name": "Context Analysis",
                "description": "Analyze document context and coherence",
                "estimated_time_seconds": 25,
                "enabled_by_default": False
            },
            {
                "type": "structure",
                "name": "Structure Analysis",
                "description": "Analyze document structure and identify missing fields",
                "estimated_time_seconds": 25,
                "enabled_by_default": False
            },
            {
                "type": "complete",
                "name": "Complete Enhancement",
                "description": "Apply all available enhancements",
                "estimated_time_seconds": 30,
                "enabled_by_default": False
            }
        ],
        "note": "Enhancement times are estimates and may vary based on document size"
    }


@router.get("/config/quality-thresholds", response_model=dict)
async def get_quality_thresholds():
    """
    Get configured quality thresholds

    Returns:
        Quality and confidence thresholds
    """
    return {
        "thresholds": {
            "image_quality": {
                "minimum": 30,
                "default": 30,
                "description": "Minimum image quality score to proceed with OCR (0-100)"
            },
            "confidence": {
                "automatic_processing": 80,
                "default": 80,
                "description": "Minimum confidence for automatic processing (0-100)"
            }
        },
        "confidence_weights": {
            "image_quality": 0.20,
            "ocr_confidence": 0.30,
            "grammar": 0.20,
            "context": 0.20,
            "structure": 0.10
        },
        "priority_levels": {
            "high": "< 60% confidence",
            "medium": "60-80% confidence",
            "low": "> 80% confidence"
        }
    }


@router.get("/config/processing-limits", response_model=dict)
async def get_processing_limits():
    """
    Get processing limits and constraints

    Returns:
        Processing limits and timeouts
    """
    return {
        "limits": {
            "max_file_size_mb": settings.storage_max_size_mb,
            "optimal_file_size_mb": settings.image_optimal_size_mb,
            "supported_formats": ["PDF", "JPG", "JPEG", "PNG", "TIFF"],
            "supported_languages": ["en", "zh"]
        },
        "timeouts": {
            "quality_check_seconds": 1,
            "ocr_processing_seconds": 6,
            "llm_enhancement_seconds": 30,
            "total_timeout_seconds": settings.processing_timeout
        },
        "api": {
            "timeout_seconds": settings.api_timeout,
            "manual_review_threshold": settings.manual_review_threshold
        }
    }