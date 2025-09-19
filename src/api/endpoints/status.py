"""
Document status and result endpoints
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse

from src.models.document import ProcessingStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# Import shared storage from documents endpoint
from src.api.endpoints.documents import processing_results, processing_documents


@router.get("/{document_id}/status", response_model=dict)
async def get_document_status(
    document_id: str = Path(..., description="Document ID to check status")
):
    """
    Get the processing status of a document

    Args:
        document_id: Unique document identifier

    Returns:
        Current processing status
    """
    try:
        # Check if document exists
        if document_id not in processing_documents:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )

        document = processing_documents[document_id]

        # Check if processing is complete
        result = processing_results.get(document_id)

        response = {
            "document_id": document_id,
            "status": document.processing_status.value,
            "filename": document.filename,
            "submission_time": document.submission_time.isoformat(),
            "processing_start_time": document.processing_start_time.isoformat() if document.processing_start_time else None,
            "processing_end_time": document.processing_end_time.isoformat() if document.processing_end_time else None,
        }

        # Add progress information if available
        if result:
            response["progress"] = {
                "quality_check": result.processing_metrics.get("quality_check_time") is not None,
                "ocr_processing": result.processing_metrics.get("ocr_processing_time") is not None,
                "enhancements_applied": result.processing_metrics.get("enhancements_applied", []),
                "total_time": result.processing_metrics.get("total_processing_time")
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/result", response_model=dict)
async def get_document_result(
    document_id: str = Path(..., description="Document ID to get results"),
    include_enhanced: bool = True
):
    """
    Get the processing results for a document

    Args:
        document_id: Unique document identifier
        include_enhanced: Include enhanced text in response

    Returns:
        Complete processing results
    """
    try:
        # Check if result exists
        if document_id not in processing_results:
            # Check if document exists but not processed
            if document_id in processing_documents:
                document = processing_documents[document_id]
                if document.processing_status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Document {document_id} is still processing"
                    )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Results not found for document {document_id}"
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document {document_id} not found"
                )

        result = processing_results[document_id]

        response = {
            "document_id": document_id,
            "status": result.status.value,
            "extracted_text": result.extracted_text,
            "word_count": len(result.extracted_text.split()),
            "processing_metrics": result.processing_metrics,
            "created_at": result.created_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None
        }

        # Add enhanced text if requested and available
        if include_enhanced and result.enhanced_text:
            response["enhanced_text"] = result.enhanced_text
            response["corrections_made"] = result.corrections_made[:10]  # Limit to 10

        # Add error message if failed
        if result.error_message:
            response["error_message"] = result.error_message

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/confidence", response_model=dict)
async def get_confidence_breakdown(
    document_id: str = Path(..., description="Document ID to get confidence breakdown")
):
    """
    Get detailed confidence breakdown for a document

    Args:
        document_id: Unique document identifier

    Returns:
        Detailed confidence scores and routing decision
    """
    try:
        # Check if result exists
        if document_id not in processing_results:
            raise HTTPException(
                status_code=404,
                detail=f"Results not found for document {document_id}"
            )

        result = processing_results[document_id]

        # Check if confidence report exists
        if not result.confidence_report:
            raise HTTPException(
                status_code=404,
                detail=f"Confidence report not available for document {document_id}"
            )

        confidence = result.confidence_report

        return {
            "document_id": document_id,
            "confidence_scores": {
                "image_quality": confidence.image_quality_score,
                "ocr_confidence": confidence.ocr_confidence_score,
                "grammar": confidence.grammar_score,
                "context": confidence.context_score,
                "structure": confidence.structure_score,
                "final": confidence.final_confidence
            },
            "routing": {
                "decision": confidence.routing_decision,
                "priority_level": confidence.priority_level,
                "automatic_processing": confidence.routing_decision == "automatic"
            },
            "issues_detected": confidence.issues_detected,
            "weights": {
                "image_quality": 0.20,
                "ocr_confidence": 0.30,
                "grammar": 0.20,
                "context": 0.20,
                "structure": 0.10
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting confidence breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/enhancements", response_model=dict)
async def get_enhancement_details(
    document_id: str = Path(..., description="Document ID to get enhancement details")
):
    """
    Get detailed LLM enhancement results

    Args:
        document_id: Unique document identifier

    Returns:
        LLM enhancement details including corrections and suggestions
    """
    try:
        # Check if result exists
        if document_id not in processing_results:
            raise HTTPException(
                status_code=404,
                detail=f"Results not found for document {document_id}"
            )

        result = processing_results[document_id]

        # Get enhancements applied
        enhancements_applied = result.processing_metrics.get("enhancements_applied", [])

        if not enhancements_applied:
            return {
                "document_id": document_id,
                "enhancements_applied": [],
                "message": "No LLM enhancements were applied to this document"
            }

        response = {
            "document_id": document_id,
            "enhancements_applied": enhancements_applied,
            "corrections": result.corrections_made,
            "total_corrections": len(result.corrections_made),
            "enhancement_timing": result.processing_metrics.get("llm_enhancement_time", {}),
            "enhanced_text_available": result.enhanced_text is not None
        }

        # Add enhancement breakdown
        enhancement_details = {}
        for enhancement in enhancements_applied:
            if enhancement in result.processing_metrics.get("llm_enhancement_time", {}):
                enhancement_details[enhancement] = {
                    "processing_time": result.processing_metrics["llm_enhancement_time"][enhancement],
                    "corrections_count": sum(1 for c in result.corrections_made if c.get("type") == enhancement)
                }

        response["enhancement_details"] = enhancement_details

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhancement details: {e}")
        raise HTTPException(status_code=500, detail=str(e))