"""
PDF processing result models for page-level tracking
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PageStatus(str, Enum):
    """Status of individual page processing"""
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CORRUPTED = "corrupted"


class PageOCRResult(BaseModel):
    """OCR result for a single page"""
    page_number: int
    status: PageStatus
    text: Optional[str] = None
    confidence: Optional[float] = None
    word_count: Optional[int] = None
    processing_time_ms: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0


class PageMetadata(BaseModel):
    """Metadata for a PDF page"""
    page_number: int
    width: int
    height: int
    rotation: int = 0
    has_text: bool = False
    has_images: bool = False
    dpi: Optional[int] = None


class PDFProcessingResult(BaseModel):
    """
    Page-level tracking for PDF processing
    Handles multi-page PDFs with page-by-page OCR results
    """
    document_id: str
    status: str = "pending"  # pending, processing, success, partial_success, failed

    # Page tracking
    total_pages: int
    successful_pages: List[int] = Field(default_factory=list)
    failed_pages: List[int] = Field(default_factory=list)
    skipped_pages: List[int] = Field(default_factory=list)

    # Page results
    page_results: Dict[int, PageOCRResult] = Field(default_factory=dict)
    page_errors: Dict[int, str] = Field(default_factory=dict)
    page_metadata: Dict[int, PageMetadata] = Field(default_factory=dict)

    # Processing details
    processing_time_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Configuration used
    continue_on_error: bool = True
    max_retries_per_page: int = 2
    parallel_workers: int = 4
    timeout_per_page: int = 30  # seconds

    # Aggregate results
    combined_text: Optional[str] = None
    average_confidence: Optional[float] = None
    total_word_count: int = 0

    def add_page_result(self, page_number: int, result: PageOCRResult):
        """Add result for a specific page"""
        self.page_results[page_number] = result

        if result.status == PageStatus.SUCCESS:
            if page_number not in self.successful_pages:
                self.successful_pages.append(page_number)
            # Remove from failed if it was there (retry succeeded)
            if page_number in self.failed_pages:
                self.failed_pages.remove(page_number)
        elif result.status in [PageStatus.ERROR, PageStatus.CORRUPTED, PageStatus.TIMEOUT]:
            if page_number not in self.failed_pages:
                self.failed_pages.append(page_number)
            self.page_errors[page_number] = result.error or result.error_code or "Unknown error"
        elif result.status == PageStatus.SKIPPED:
            if page_number not in self.skipped_pages:
                self.skipped_pages.append(page_number)

        # Sort the lists
        self.successful_pages.sort()
        self.failed_pages.sort()
        self.skipped_pages.sort()

        # Update status
        self._update_status()

    def add_page_metadata(self, page_number: int, metadata: PageMetadata):
        """Add metadata for a specific page"""
        self.page_metadata[page_number] = metadata

    def _update_status(self):
        """Update overall status based on page results"""
        processed = len(self.page_results)

        if processed == 0:
            self.status = "pending"
        elif processed < self.total_pages:
            self.status = "processing"
        elif len(self.successful_pages) == self.total_pages:
            self.status = "success"
        elif len(self.successful_pages) == 0:
            self.status = "failed"
        else:
            self.status = "partial_success"

    def combine_results(self):
        """Combine all successful page results into aggregate results"""
        if not self.successful_pages:
            return

        # Combine text from all successful pages in order
        text_parts = []
        total_confidence = 0
        confidence_count = 0
        total_words = 0

        for page_num in sorted(self.successful_pages):
            if page_num in self.page_results:
                result = self.page_results[page_num]
                if result.text:
                    text_parts.append(f"[Page {page_num}]\n{result.text}")
                    if result.word_count:
                        total_words += result.word_count
                    if result.confidence:
                        total_confidence += result.confidence
                        confidence_count += 1

        self.combined_text = "\n\n".join(text_parts)
        self.total_word_count = total_words

        if confidence_count > 0:
            self.average_confidence = total_confidence / confidence_count

    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary"""
        processing_time = None
        if self.started_at and self.completed_at:
            processing_time = (self.completed_at - self.started_at).total_seconds()

        return {
            "status": self.status,
            "total_pages": self.total_pages,
            "successful_pages": len(self.successful_pages),
            "failed_pages": len(self.failed_pages),
            "skipped_pages": len(self.skipped_pages),
            "success_rate": (len(self.successful_pages) / self.total_pages * 100)
            if self.total_pages > 0 else 0,
            "average_confidence": self.average_confidence,
            "total_word_count": self.total_word_count,
            "processing_time_seconds": processing_time,
            "pages_with_errors": self.page_errors
        }

    def get_page_range_text(self, start_page: int, end_page: int) -> Optional[str]:
        """Get combined text for a specific page range"""
        text_parts = []
        for page_num in range(start_page, end_page + 1):
            if page_num in self.page_results:
                result = self.page_results[page_num]
                if result.status == PageStatus.SUCCESS and result.text:
                    text_parts.append(f"[Page {page_num}]\n{result.text}")

        return "\n\n".join(text_parts) if text_parts else None

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format"""
        response = {
            "status": self.status,
            "document_id": self.document_id,
            "total_pages": self.total_pages,
            "summary": self.get_summary(),
            "page_results": {},
            # Add fields expected by ocr endpoint
            "successful_pages": len(self.successful_pages),
            "failed_pages": self.failed_pages,
            "average_confidence": self.average_confidence,
            "total_word_count": self.total_word_count
        }

        # Add error field if there are failures
        if self.status == "failed" and self.page_errors:
            # Get first error message for general error field
            first_error = next(iter(self.page_errors.values()), "Processing failed")
            response["error"] = first_error

        # Include page results
        for page_num, result in self.page_results.items():
            response["page_results"][page_num] = {
                "status": result.status,
                "text": result.text if result.status == PageStatus.SUCCESS else None,
                "confidence": result.confidence,
                "word_count": result.word_count,
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
                "retry_count": result.retry_count
            }

        # Include combined text if requested
        if self.combined_text:
            response["combined_text"] = self.combined_text

        return response

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }