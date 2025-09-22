"""
Batch processing models for handling multiple documents
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class BatchStatus(str, Enum):
    """Status of a batch job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"
    CANCELLED = "cancelled"


class DocumentStatus(str, Enum):
    """Status of individual document in batch"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class ErrorDetail(BaseModel):
    """Error details for failed document processing"""
    error_code: str
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None


class ProcessingResult(BaseModel):
    """Result of processing a single document"""
    document_id: str
    status: DocumentStatus
    format_detected: Optional[str] = None
    ocr_text: Optional[str] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None
    error: Optional[ErrorDetail] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchDocument(BaseModel):
    """Document to be processed in batch"""
    document_id: str
    file: str  # Base64 encoded file
    format_hint: Optional[str] = None
    processing_options: Optional[Dict[str, Any]] = None


class BatchJob(BaseModel):
    """
    Batch processing job entity
    Handles multiple document processing with state management
    """
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: BatchStatus = BatchStatus.PENDING
    documents: List[BatchDocument]
    results: Dict[str, ProcessingResult] = Field(default_factory=dict)
    errors: Dict[str, ErrorDetail] = Field(default_factory=dict)

    # Processing options
    fail_fast: bool = False
    max_workers: int = 4
    timeout_seconds: int = 180

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Statistics
    total_documents: int = 0
    processed_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        self.total_documents = len(self.documents)

    def start_processing(self):
        """Mark job as started"""
        self.status = BatchStatus.PROCESSING
        self.started_at = datetime.now()

    def add_result(self, document_id: str, result: ProcessingResult):
        """Add processing result for a document"""
        self.results[document_id] = result
        self.processed_documents += 1

        if result.status == DocumentStatus.SUCCESS:
            self.successful_documents += 1
        elif result.status in [DocumentStatus.FAILED, DocumentStatus.ERROR]:
            self.failed_documents += 1
            if result.error:
                self.errors[document_id] = result.error

            # Check fail-fast option
            if self.fail_fast:
                self.status = BatchStatus.FAILED
                self.completed_at = datetime.now()
                return True  # Signal to stop processing

        # Check if all documents are processed
        if self.processed_documents >= self.total_documents:
            self.complete_processing()

        return False  # Continue processing

    def complete_processing(self):
        """Mark job as completed and determine final status"""
        self.completed_at = datetime.now()

        if self.failed_documents == 0:
            self.status = BatchStatus.COMPLETED
        elif self.successful_documents == 0:
            self.status = BatchStatus.FAILED
        else:
            self.status = BatchStatus.PARTIAL_SUCCESS

    def cancel(self):
        """Cancel the batch job"""
        self.status = BatchStatus.CANCELLED
        self.completed_at = datetime.now()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of batch processing"""
        processing_time = None
        if self.started_at and self.completed_at:
            processing_time = (self.completed_at - self.started_at).total_seconds()

        return {
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total_documents,
            "processed": self.processed_documents,
            "successful": self.successful_documents,
            "failed": self.failed_documents,
            "processing_time_seconds": processing_time,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def add_error(self, document_id: str, error: ErrorDetail):
        """Add error for a document"""
        self.errors[document_id] = error
        self.failed_documents += 1
        self.processed_documents += 1

        # Check if all documents are processed
        if self.processed_documents >= self.total_documents:
            self.complete_processing()

    def complete(self):
        """Alias for complete_processing for compatibility"""
        self.complete_processing()

    def to_response(self) -> Dict[str, Any]:
        """Convert to API response format"""
        processing_time_ms = None
        if self.started_at and self.completed_at:
            processing_time_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "total_documents": self.total_documents,
            "successful_documents": self.successful_documents,
            "failed_documents": self.failed_documents,
            "document_results": {doc_id: result.dict() if hasattr(result, 'dict') else result for doc_id, result in self.results.items()},
            "document_errors": {doc_id: error.dict() if hasattr(error, 'dict') else error for doc_id, error in self.errors.items()},
            "processing_time_ms": processing_time_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def get_multi_status_response(self) -> Dict[str, Any]:
        """
        Get 207 Multi-Status response format
        Used for batch endpoints returning mixed results
        """
        return {
            "status": self.status,
            "summary": self.get_summary(),
            "results": [
                {
                    "document_id": doc.document_id,
                    "status": self.results.get(doc.document_id, ProcessingResult(
                        document_id=doc.document_id,
                        status=DocumentStatus.PENDING
                    )).status,
                    "result": self.results.get(doc.document_id).dict(exclude_none=True)
                    if doc.document_id in self.results else None,
                    "error": self.errors.get(doc.document_id).dict()
                    if doc.document_id in self.errors else None
                }
                for doc in self.documents
            ]
        }

    class Config:
        use_enum_values = True