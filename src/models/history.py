"""
Processing history models for tracking document processing
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid


class ProcessingHistory(BaseModel):
    """
    Processing history entity with auto-expiry
    Tracks document processing for 7 days
    """
    history_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    user_id: Optional[str] = None

    # Processing details
    file_format: str
    file_name: str
    file_size_bytes: int
    processing_time_ms: float
    success: bool

    # Results
    result_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Timestamps
    processed_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(default_factory=lambda: datetime.now() + timedelta(days=7))

    # Metadata
    source_type: str = "file"  # file, obs_url, etc.
    format_detected: Optional[str] = None
    pages_processed: Optional[int] = None
    ocr_confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        # Auto-calculate expires_at if not provided
        if 'expires_at' not in data:
            data['expires_at'] = datetime.now() + timedelta(days=7)
        super().__init__(**data)

    @property
    def is_expired(self) -> bool:
        """Check if this history record has expired"""
        return datetime.now() > self.expires_at

    @property
    def days_until_expiry(self) -> float:
        """Calculate days remaining until expiry"""
        delta = self.expires_at - datetime.now()
        return max(0, delta.total_seconds() / 86400)

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "document_id": self.document_id,
            "processing_history": {
                "processed_at": self.processed_at.isoformat(),
                "file_format": self.file_format,
                "file_name": self.file_name,
                "file_size_bytes": self.file_size_bytes,
                "processing_time_ms": self.processing_time_ms,
                "success": self.success,
                "result_summary": self.result_summary,
                "error_code": self.error_code,
                "format_detected": self.format_detected,
                "pages_processed": self.pages_processed,
                "ocr_confidence": self.ocr_confidence
            },
            "metadata": {
                "expires_at": self.expires_at.isoformat(),
                "days_until_expiry": round(self.days_until_expiry, 2),
                "retrievable_until": self.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                **self.metadata
            }
        }

    @classmethod
    def from_processing_result(
        cls,
        document_id: str,
        file_name: str,
        file_format: str,
        file_size: int,
        processing_time_ms: float,
        success: bool,
        result_summary: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> "ProcessingHistory":
        """Create history from processing result"""
        return cls(
            document_id=document_id,
            file_name=file_name,
            file_format=file_format,
            file_size_bytes=file_size,
            processing_time_ms=processing_time_ms,
            success=success,
            result_summary=result_summary,
            error_code=error_code,
            **kwargs
        )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HistoryQuery(BaseModel):
    """Query parameters for history retrieval"""
    document_id: Optional[str] = None
    user_id: Optional[str] = None
    file_format: Optional[str] = None
    success: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
    include_expired: bool = False


class HistoryStatistics(BaseModel):
    """Statistics from processing history"""
    total_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    success_rate: float = 0.0
    format_distribution: Dict[str, int] = Field(default_factory=dict)
    average_processing_time_ms: float = 0.0
    total_bytes_processed: int = 0
    active_records: int = 0
    expired_records: int = 0

    def calculate_from_records(self, records: list["ProcessingHistory"]):
        """Calculate statistics from a list of history records"""
        if not records:
            return

        self.total_records = len(records)
        self.successful_records = sum(1 for r in records if r.success)
        self.failed_records = self.total_records - self.successful_records
        self.success_rate = (self.successful_records / self.total_records * 100) if self.total_records > 0 else 0

        # Format distribution
        for record in records:
            format_key = record.file_format
            self.format_distribution[format_key] = self.format_distribution.get(format_key, 0) + 1

        # Average processing time
        total_time = sum(r.processing_time_ms for r in records)
        self.average_processing_time_ms = total_time / self.total_records if self.total_records > 0 else 0

        # Total bytes
        self.total_bytes_processed = sum(r.file_size_bytes for r in records)

        # Active vs expired
        now = datetime.now()
        self.active_records = sum(1 for r in records if r.expires_at > now)
        self.expired_records = self.total_records - self.active_records