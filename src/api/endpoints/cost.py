"""
Cost estimation endpoints
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.processing_orchestrator import ProcessingOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


class CostEstimateRequest(BaseModel):
    """Request model for cost estimation"""
    document_size_mb: float = Field(..., gt=0, le=10, description="Document size in MB")
    enhancement_types: List[str] = Field(default=[], description="List of enhancements to apply")
    num_documents: int = Field(default=1, gt=0, description="Number of documents to process")


class CostEstimateResponse(BaseModel):
    """Response model for cost estimation"""
    per_document: dict
    total: dict
    processing_time: dict
    recommendations: List[str]


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_processing_cost(request: CostEstimateRequest):
    """
    Estimate processing cost and time

    Args:
        request: Cost estimation parameters

    Returns:
        Detailed cost and time estimates
    """
    try:
        orchestrator = ProcessingOrchestrator()

        # Get per-document estimate
        per_doc_estimate = orchestrator.estimate_processing_cost(
            document_size_mb=request.document_size_mb,
            enhancement_types=request.enhancement_types
        )

        # Calculate totals
        total_estimate = {
            "estimated_ocr_cost": round(per_doc_estimate["estimated_ocr_cost"] * request.num_documents, 4),
            "estimated_llm_cost": round(per_doc_estimate["estimated_llm_cost"] * request.num_documents, 4),
            "estimated_total_cost": round(per_doc_estimate["estimated_total_cost"] * request.num_documents, 4),
            "estimated_llm_tokens": per_doc_estimate["estimated_llm_tokens"] * request.num_documents
        }

        # Processing time breakdown
        processing_time = {
            "per_document_seconds": per_doc_estimate["estimated_total_time"],
            "total_seconds": per_doc_estimate["estimated_total_time"] * request.num_documents,
            "breakdown": {
                "quality_check": per_doc_estimate["estimated_quality_time"],
                "ocr_processing": per_doc_estimate["estimated_ocr_time"],
                "llm_enhancement": per_doc_estimate["estimated_llm_time"]
            }
        }

        # Generate recommendations
        recommendations = []

        if request.document_size_mb > 7:
            recommendations.append("Consider optimizing image size to < 7MB for better performance")

        if len(request.enhancement_types) > 2:
            recommendations.append("Multiple enhancements will increase processing time significantly")

        if request.num_documents > 10:
            recommendations.append("Consider batch processing for large document sets")

        if not request.enhancement_types:
            recommendations.append("No LLM enhancements selected - processing will be faster but less accurate")

        return CostEstimateResponse(
            per_document=per_doc_estimate,
            total=total_estimate,
            processing_time=processing_time,
            recommendations=recommendations
        )

    except Exception as e:
        logger.error(f"Error estimating cost: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing", response_model=dict)
async def get_pricing_information():
    """
    Get pricing information for services

    Returns:
        Pricing details for OCR and LLM services
    """
    return {
        "ocr": {
            "provider": "Huawei OCR",
            "pricing_model": "per_document",
            "estimated_cost_per_mb": 0.01,
            "note": "Actual pricing may vary based on contract"
        },
        "llm": {
            "provider": "DeepSeek V3.1 (Huawei ModelArts MAAS)",
            "pricing_model": "per_token",
            "estimated_cost_per_1k_tokens": 0.002,
            "average_tokens_per_page": 500,
            "note": "Token usage varies based on document content and enhancement type"
        },
        "storage": {
            "provider": "Huawei OBS",
            "retention_days": 30,
            "estimated_cost_per_gb_month": 0.023
        },
        "disclaimer": "These are estimated costs. Actual costs may vary based on usage and contract terms."
    }


@router.get("/usage/summary", response_model=dict)
async def get_usage_summary():
    """
    Get current usage summary (mock data for demo)

    Returns:
        Usage statistics for the current period
    """
    # Import shared storage to calculate actual stats
    from src.api.endpoints.documents import processing_results

    total_documents = len(processing_results)
    total_tokens = sum(
        r.processing_metrics.get("llm_tokens_used", 0)
        for r in processing_results.values()
    )

    # Calculate costs (mock)
    ocr_cost = total_documents * 0.01
    llm_cost = (total_tokens / 1000) * 0.002

    return {
        "period": "current_month",
        "usage": {
            "documents_processed": total_documents,
            "ocr_calls": total_documents,
            "llm_tokens_used": total_tokens,
            "storage_used_mb": total_documents * 2  # Rough estimate
        },
        "costs": {
            "ocr_cost": round(ocr_cost, 4),
            "llm_cost": round(llm_cost, 4),
            "storage_cost": 0.0,  # Mock
            "total_cost": round(ocr_cost + llm_cost, 4)
        },
        "limits": {
            "monthly_document_limit": 10000,
            "monthly_token_limit": 10000000,
            "storage_limit_gb": 100
        },
        "note": "This is mock data for demonstration purposes"
    }