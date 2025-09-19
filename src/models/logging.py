"""Processing log model for audit trail."""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of processing events."""
    DOCUMENT_UPLOADED = "document_uploaded"
    QUALITY_ASSESSED = "quality_assessed"
    OCR_STARTED = "ocr_started"
    OCR_COMPLETED = "ocr_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    CONFIDENCE_CALCULATED = "confidence_calculated"
    ROUTING_DECIDED = "routing_decided"
    QUEUED_FOR_REVIEW = "queued_for_review"
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    ERROR_OCCURRED = "error_occurred"


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProcessingLog(BaseModel):
    """Log entry for document processing audit trail."""

    # Log metadata
    id: str = Field(..., description="Log entry identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    level: LogLevel = Field(default=LogLevel.INFO, description="Log level")

    # Event information
    event_type: EventType = Field(..., description="Type of processing event")
    event_name: str = Field(..., description="Human-readable event name")
    event_description: str = Field(..., description="Detailed event description")

    # Document reference
    document_id: str = Field(..., description="Associated document ID")
    processing_stage: str = Field(..., description="Current processing stage")

    # Timing information
    duration_ms: Optional[int] = Field(None, description="Event duration in milliseconds")
    start_time: Optional[datetime] = Field(None, description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")

    # Event details
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional event details")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")

    # Error information (if applicable)
    error_code: Optional[str] = Field(None, description="Error code if event failed")
    error_message: Optional[str] = Field(None, description="Error message if event failed")
    error_stack: Optional[str] = Field(None, description="Error stack trace if available")

    # User/system information
    user_id: Optional[str] = Field(None, description="User ID if applicable")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    service_name: Optional[str] = Field(None, description="Service that generated the log")

    @property
    def is_error(self) -> bool:
        """Check if this is an error log."""
        return self.level in [LogLevel.ERROR, LogLevel.CRITICAL] or self.error_code is not None

    @property
    def is_terminal_event(self) -> bool:
        """Check if this is a terminal event."""
        return self.event_type in [
            EventType.PROCESSING_COMPLETED,
            EventType.PROCESSING_FAILED,
            EventType.REVIEW_COMPLETED
        ]

    def calculate_duration(self) -> Optional[int]:
        """Calculate duration from start and end times."""
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds() * 1000
            return int(duration)
        return self.duration_ms

    @classmethod
    def create_event(
        cls,
        document_id: str,
        event_type: EventType,
        stage: str,
        description: str,
        **kwargs
    ) -> "ProcessingLog":
        """Create a new log event.

        Args:
            document_id: Document identifier
            event_type: Type of event
            stage: Processing stage
            description: Event description
            **kwargs: Additional fields for the log entry

        Returns:
            New ProcessingLog instance
        """
        import uuid

        # Generate log ID
        log_id = str(uuid.uuid4())

        # Determine event name
        event_names = {
            EventType.DOCUMENT_UPLOADED: "Document Uploaded",
            EventType.QUALITY_ASSESSED: "Quality Assessment Complete",
            EventType.OCR_STARTED: "OCR Processing Started",
            EventType.OCR_COMPLETED: "OCR Processing Complete",
            EventType.VALIDATION_STARTED: "Validation Started",
            EventType.VALIDATION_COMPLETED: "Validation Complete",
            EventType.CONFIDENCE_CALCULATED: "Confidence Score Calculated",
            EventType.ROUTING_DECIDED: "Routing Decision Made",
            EventType.QUEUED_FOR_REVIEW: "Queued for Manual Review",
            EventType.REVIEW_STARTED: "Manual Review Started",
            EventType.REVIEW_COMPLETED: "Manual Review Complete",
            EventType.PROCESSING_COMPLETED: "Processing Complete",
            EventType.PROCESSING_FAILED: "Processing Failed",
            EventType.ERROR_OCCURRED: "Error Occurred"
        }

        event_name = event_names.get(event_type, str(event_type))

        # Determine log level based on event type
        if event_type in [EventType.PROCESSING_FAILED, EventType.ERROR_OCCURRED]:
            level = LogLevel.ERROR
        elif event_type == EventType.QUEUED_FOR_REVIEW:
            level = LogLevel.WARNING
        else:
            level = LogLevel.INFO

        return cls(
            id=log_id,
            document_id=document_id,
            event_type=event_type,
            event_name=event_name,
            event_description=description,
            processing_stage=stage,
            level=kwargs.pop("level", level),
            **kwargs
        )

    @classmethod
    def create_error(
        cls,
        document_id: str,
        stage: str,
        error_code: str,
        error_message: str,
        error_stack: Optional[str] = None,
        **kwargs
    ) -> "ProcessingLog":
        """Create an error log entry.

        Args:
            document_id: Document identifier
            stage: Processing stage where error occurred
            error_code: Error code
            error_message: Error message
            error_stack: Optional stack trace
            **kwargs: Additional fields

        Returns:
            New error ProcessingLog instance
        """
        return cls.create_event(
            document_id=document_id,
            event_type=EventType.ERROR_OCCURRED,
            stage=stage,
            description=f"Error in {stage}: {error_message}",
            level=LogLevel.ERROR,
            error_code=error_code,
            error_message=error_message,
            error_stack=error_stack,
            **kwargs
        )

    def to_json_log(self) -> Dict[str, Any]:
        """Convert to JSON format for logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "event_type": self.event_type.value,
            "document_id": self.document_id,
            "stage": self.processing_stage,
            "message": self.event_description,
            "duration_ms": self.duration_ms or self.calculate_duration(),
            "details": self.details,
            "metrics": self.metrics,
            "error": {
                "code": self.error_code,
                "message": self.error_message,
                "stack": self.error_stack
            } if self.is_error else None,
            "metadata": {
                "log_id": self.id,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "service": self.service_name
            }
        }

    def to_audit_entry(self) -> Dict[str, Any]:
        """Convert to audit trail entry."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "document_id": self.document_id,
            "event": self.event_name,
            "stage": self.processing_stage,
            "duration_ms": self.duration_ms or self.calculate_duration(),
            "success": not self.is_error,
            "user_id": self.user_id
        }

    class Config:
        """Pydantic configuration."""
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }