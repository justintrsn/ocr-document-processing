"""Document model for OCR processing."""
import hashlib
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class DocumentFormat(str, Enum):
    """Supported document formats."""
    PDF = "pdf"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"  # Passed all checks, automatic processing
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"  # Needs manual review (low confidence)
    IN_REVIEW = "in_review"  # Currently being reviewed
    REVIEWED = "reviewed"  # Manual review completed


class Document(BaseModel):
    """Document model with validation and state management."""

    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    format: DocumentFormat = Field(..., description="Document format")
    size_bytes: int = Field(..., description="File size in bytes")
    submission_time: datetime = Field(default_factory=datetime.utcnow, description="Document submission timestamp")
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="Current processing status")
    file_path: Path = Field(..., description="Path to stored document file")
    checksum: str = Field(..., description="SHA256 checksum of the file")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Processing timestamps
    processing_start_time: Optional[datetime] = None
    processing_end_time: Optional[datetime] = None

    # Processing results
    confidence_score: Optional[float] = None
    routing_decision: Optional[str] = None
    error_message: Optional[str] = None

    @validator("format", pre=True)
    def normalize_format(cls, v):
        """Normalize format to lowercase."""
        if isinstance(v, str):
            v = v.lower()
            if v == "jpeg":
                v = "jpg"  # Normalize jpeg to jpg
        return v

    @validator("size_bytes")
    def validate_size(cls, v):
        """Validate file size is within limits."""
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if v > max_size:
            raise ValueError(f"File size {v} bytes exceeds maximum of {max_size} bytes (10MB)")
        if v <= 0:
            raise ValueError("File size must be positive")
        return v

    @validator("checksum")
    def validate_checksum(cls, v):
        """Validate checksum format."""
        if not v or len(v) != 64:  # SHA256 produces 64 character hex string
            raise ValueError("Invalid SHA256 checksum")
        return v.lower()

    @validator("confidence_score")
    def validate_confidence(cls, v):
        """Validate confidence score range."""
        if v is not None and not 0 <= v <= 100:
            raise ValueError("Confidence score must be between 0 and 100")
        return v

    def can_transition_to(self, new_status: ProcessingStatus) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            ProcessingStatus.PENDING: [
                ProcessingStatus.PROCESSING,
                ProcessingStatus.FAILED
            ],
            ProcessingStatus.PROCESSING: [
                ProcessingStatus.COMPLETED,
                ProcessingStatus.MANUAL_REVIEW,
                ProcessingStatus.FAILED
            ],
            ProcessingStatus.COMPLETED: [
                ProcessingStatus.MANUAL_REVIEW  # Can still be queued for audit
            ],
            ProcessingStatus.MANUAL_REVIEW: [
                ProcessingStatus.IN_REVIEW,
                ProcessingStatus.FAILED
            ],
            ProcessingStatus.IN_REVIEW: [
                ProcessingStatus.REVIEWED,
                ProcessingStatus.MANUAL_REVIEW,  # Send back to queue
                ProcessingStatus.FAILED
            ],
            ProcessingStatus.REVIEWED: [],  # Terminal state
            ProcessingStatus.FAILED: [
                ProcessingStatus.PENDING  # Allow retry
            ]
        }

        return new_status in valid_transitions.get(self.processing_status, [])

    def transition_to(self, new_status: ProcessingStatus) -> None:
        """Transition to a new status with validation."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid status transition from {self.processing_status} to {new_status}"
            )

        # Update timestamps
        if new_status == ProcessingStatus.PROCESSING and not self.processing_start_time:
            self.processing_start_time = datetime.utcnow()
        elif new_status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.REVIEWED]:
            self.processing_end_time = datetime.utcnow()

        self.processing_status = new_status

    @property
    def processing_duration(self) -> Optional[float]:
        """Get processing duration in seconds."""
        if self.processing_start_time and self.processing_end_time:
            return (self.processing_end_time - self.processing_start_time).total_seconds()
        return None

    @property
    def is_optimal_size(self) -> bool:
        """Check if document is within optimal size range."""
        optimal_size = 7 * 1024 * 1024  # 7MB in bytes
        return self.size_bytes <= optimal_size

    @property
    def requires_manual_review(self) -> bool:
        """Check if document requires manual review."""
        return self.processing_status in [
            ProcessingStatus.MANUAL_REVIEW,
            ProcessingStatus.IN_REVIEW
        ]

    @property
    def is_terminal_state(self) -> bool:
        """Check if document is in a terminal state."""
        return self.processing_status in [
            ProcessingStatus.COMPLETED,
            ProcessingStatus.REVIEWED
        ]

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def to_summary(self) -> Dict[str, Any]:
        """Return a summary representation for API responses."""
        return {
            "id": self.id,
            "filename": self.filename,
            "format": self.format.value,
            "status": self.processing_status.value,
            "submission_time": self.submission_time.isoformat(),
            "confidence_score": self.confidence_score,
            "routing_decision": self.routing_decision,
            "processing_duration": self.processing_duration
        }

    class Config:
        """Pydantic configuration."""
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: lambda v: str(v)
        }