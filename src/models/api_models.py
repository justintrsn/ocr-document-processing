from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from src.models.document import ProcessingStatus


class ProcessDocumentResponse(BaseModel):
    document_id: str
    status: ProcessingStatus
    confidence_score: float
    message: str


class DocumentStatus(BaseModel):
    document_id: str
    status: ProcessingStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    confidence_score: Optional[float] = None


class DocumentResult(BaseModel):
    document_id: str
    status: ProcessingStatus
    confidence_score: float
    extracted_text: str
    ocr_data: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None


class ConfidenceReport(BaseModel):
    image_quality_score: float = Field(..., ge=0, le=100)
    ocr_confidence_score: float = Field(..., ge=0, le=100)
    grammar_score: float = Field(..., ge=0, le=100)
    context_score: float = Field(..., ge=0, le=100)
    structure_score: float = Field(..., ge=0, le=100)
    final_confidence: float = Field(..., ge=0, le=100)
    routing_decision: str = Field(..., description="automatic, manual_review, or rejected")
    priority_level: str = Field(default="medium", description="high, medium, or low")
    issues_detected: List[str] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """Complete result from document processing pipeline"""
    document_id: str
    status: ProcessingStatus
    confidence_report: Optional[ConfidenceReport] = None
    extracted_text: str = ""
    enhanced_text: Optional[str] = None
    corrections_made: List[Dict[str, Any]] = Field(default_factory=list)
    processing_metrics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)