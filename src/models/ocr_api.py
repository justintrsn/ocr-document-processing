"""
OCR API Request and Response Models
"""

from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    """Source input type"""
    FILE = "file"
    OBS_URL = "obs_url"


class ReturnFormat(str, Enum):
    """Response format options"""
    FULL = "full"           # Complete response with all details
    MINIMAL = "minimal"     # Essential data only
    OCR_ONLY = "ocr_only"   # Just OCR results


class SourceInput(BaseModel):
    """Source input configuration"""
    type: SourceType
    file: Optional[str] = Field(None, description="Base64 encoded file content")
    obs_url: Optional[str] = Field(None, description="OBS URL (obs://bucket/path)")

    @validator('file')
    def validate_file(cls, v, values):
        if values.get('type') == SourceType.FILE and not v:
            raise ValueError("file is required when type is 'file'")
        return v

    @validator('obs_url')
    def validate_obs_url(cls, v, values):
        if values.get('type') == SourceType.OBS_URL and not v:
            raise ValueError("obs_url is required when type is 'obs_url'")
        if v and not v.startswith('obs://'):
            raise ValueError("obs_url must start with 'obs://'")
        return v


class ProcessingOptions(BaseModel):
    """Processing configuration options"""
    # Quality check is always performed - it gates OCR processing
    enable_ocr: bool = Field(True, description="Perform OCR extraction")
    enable_enhancement: bool = Field(False, description="Apply LLM enhancement (comprehensive single-pass improvement)")
    enable_preprocessing: bool = Field(True, description="Apply preprocessing to all supported formats including PDFs (rotation, contrast, noise reduction, etc.)")
    return_format: ReturnFormat = Field(ReturnFormat.FULL,
                                        description="Response format")


class ThresholdSettings(BaseModel):
    """Threshold settings for routing decisions"""
    image_quality_threshold: float = Field(60.0, ge=0, le=100,
                                           description="Minimum image quality score to proceed with OCR")
    confidence_threshold: float = Field(80.0, ge=0, le=100,
                                       description="Minimum confidence for automatic routing")


class OCRRequest(BaseModel):
    """Main OCR API request model"""
    source: SourceInput
    processing_options: ProcessingOptions = Field(default_factory=ProcessingOptions)
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)
    async_processing: bool = Field(False, description="Process asynchronously")

    class Config:
        schema_extra = {
            "example": {
                "source": {
                    "type": "file",
                    "file": "<base64_encoded_content>"
                },
                "processing_options": {
                    "enable_ocr": True,
                    "enable_enhancement": False,
                    "return_format": "full"
                },
                "thresholds": {
                    "image_quality_threshold": 60,
                    "confidence_threshold": 80
                },
                "async_processing": False
            }
        }


# Response Models

class QualityCheckResponse(BaseModel):
    """Quality check results"""
    performed: bool
    passed: bool
    score: float
    metrics: Dict[str, float] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None


class OCRResultResponse(BaseModel):
    """OCR extraction results"""
    raw_text: str
    word_count: int
    confidence_score: float
    confidence_distribution: Dict[str, int] = Field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = Field(None,
                                                   description="Full Huawei OCR response")
    processing_time_ms: Optional[float] = None


class EnhancementResponse(BaseModel):
    """LLM enhancement results"""
    performed: bool
    enhanced_text: Optional[str] = None
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None
    tokens_used: Optional[int] = None


class ConfidenceReportResponse(BaseModel):
    """Confidence and routing analysis"""
    image_quality_score: float
    ocr_confidence_score: float
    final_confidence: float
    thresholds_applied: ThresholdSettings
    routing_decision: Literal["pass", "requires_review"]
    routing_reason: str
    quality_check_passed: bool
    confidence_check_passed: bool


class MetadataResponse(BaseModel):
    """Response metadata"""
    document_id: str
    timestamp: datetime
    version: str = "1.0"
    processing_time_ms: float


class OCRResponseFull(BaseModel):
    """Full OCR API response"""
    status: Literal["success", "failed", "processing"]
    job_id: Optional[str] = None
    quality_check: Optional[QualityCheckResponse] = None
    ocr_result: Optional[OCRResultResponse] = None
    enhancement: Optional[EnhancementResponse] = None
    confidence_report: ConfidenceReportResponse
    metadata: MetadataResponse
    error: Optional[str] = None


class OCRResponseMinimal(BaseModel):
    """Minimal OCR API response"""
    status: Literal["success", "failed", "processing"]
    extracted_text: str
    routing_decision: Literal["pass", "requires_review"]
    confidence_score: float
    document_id: str
    error: Optional[str] = None


class OCRResponseOCROnly(BaseModel):
    """OCR-only API response"""
    status: Literal["success", "failed"]
    raw_text: str
    word_count: int
    ocr_confidence: float
    processing_time_ms: float
    document_id: str
    error: Optional[str] = None


class AsyncJobResponse(BaseModel):
    """Response for async processing request"""
    status: Literal["accepted", "failed"]
    job_id: str
    message: str = "Document submitted for processing"
    estimated_time_seconds: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "status": "accepted",
                "job_id": "job_abc123def456",
                "message": "Document submitted for processing",
                "estimated_time_seconds": 30
            }
        }


class JobStatusResponse(BaseModel):
    """Job status query response"""
    job_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    progress_percentage: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None