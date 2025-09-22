"""
Error codes and messages for document processing
"""

from enum import Enum
from typing import Dict, Any, Optional


class ErrorCode(Enum):
    """Standard error codes for document processing"""

    # Format errors (4xx)
    FORMAT_NOT_SUPPORTED = "FORMAT_NOT_SUPPORTED"
    FORMAT_DETECTION_FAILED = "FORMAT_DETECTION_FAILED"
    FORMAT_CONVERSION_FAILED = "FORMAT_CONVERSION_FAILED"

    # Size and dimension errors (4xx)
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_EMPTY = "FILE_EMPTY"
    DIMENSIONS_INVALID = "DIMENSIONS_INVALID"
    DIMENSIONS_TOO_SMALL = "DIMENSIONS_TOO_SMALL"
    DIMENSIONS_TOO_LARGE = "DIMENSIONS_TOO_LARGE"

    # PDF specific errors
    PDF_CORRUPTED = "PDF_CORRUPTED"
    PDF_EMPTY = "PDF_EMPTY"
    PDF_TOO_MANY_PAGES = "PDF_TOO_MANY_PAGES"
    PDF_PAGE_NOT_FOUND = "PDF_PAGE_NOT_FOUND"
    PDF_PAGE_EXTRACTION_FAILED = "PDF_PAGE_EXTRACTION_FAILED"

    # Image errors
    IMAGE_CORRUPTED = "IMAGE_CORRUPTED"
    IMAGE_QUALITY_TOO_LOW = "IMAGE_QUALITY_TOO_LOW"
    IMAGE_COVERAGE_INSUFFICIENT = "IMAGE_COVERAGE_INSUFFICIENT"

    # Processing errors (5xx)
    OCR_FAILED = "OCR_FAILED"
    OCR_TIMEOUT = "OCR_TIMEOUT"
    OCR_NO_TEXT_FOUND = "OCR_NO_TEXT_FOUND"

    # Batch processing errors
    BATCH_SIZE_EXCEEDED = "BATCH_SIZE_EXCEEDED"
    BATCH_TIMEOUT = "BATCH_TIMEOUT"
    BATCH_PARTIAL_FAILURE = "BATCH_PARTIAL_FAILURE"

    # History errors
    HISTORY_NOT_FOUND = "HISTORY_NOT_FOUND"
    HISTORY_EXPIRED = "HISTORY_EXPIRED"
    HISTORY_DATABASE_ERROR = "HISTORY_DATABASE_ERROR"

    # General errors
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_BASE64 = "INVALID_BASE64"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


# Error messages mapping
ERROR_MESSAGES: Dict[ErrorCode, str] = {
    ErrorCode.FORMAT_NOT_SUPPORTED: "The file format is not supported. Supported formats: PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, PCX, ICO, PSD, PDF",
    ErrorCode.FORMAT_DETECTION_FAILED: "Unable to detect file format from the provided data",
    ErrorCode.FORMAT_CONVERSION_FAILED: "Failed to convert file format for processing",

    ErrorCode.FILE_TOO_LARGE: "File size exceeds the maximum limit of 10MB",
    ErrorCode.FILE_EMPTY: "The provided file is empty",
    ErrorCode.DIMENSIONS_INVALID: "Image dimensions are outside the valid range (15-30000 pixels)",
    ErrorCode.DIMENSIONS_TOO_SMALL: "Image dimensions are too small (minimum 15x15 pixels)",
    ErrorCode.DIMENSIONS_TOO_LARGE: "Image dimensions are too large (maximum 30000x30000 pixels)",

    ErrorCode.PDF_CORRUPTED: "The PDF file is corrupted and cannot be processed",
    ErrorCode.PDF_EMPTY: "The PDF file contains no pages",
    ErrorCode.PDF_TOO_MANY_PAGES: "PDF contains too many pages for automatic processing (maximum 20 pages)",
    ErrorCode.PDF_PAGE_NOT_FOUND: "The requested page does not exist in the PDF",
    ErrorCode.PDF_PAGE_EXTRACTION_FAILED: "Failed to extract the specified page from the PDF",

    ErrorCode.IMAGE_CORRUPTED: "The image file is corrupted and cannot be processed",
    ErrorCode.IMAGE_QUALITY_TOO_LOW: "Image quality is below the minimum threshold for reliable OCR",
    ErrorCode.IMAGE_COVERAGE_INSUFFICIENT: "Image contains insufficient content (too much white space)",

    ErrorCode.OCR_FAILED: "OCR processing failed",
    ErrorCode.OCR_TIMEOUT: "OCR processing timed out",
    ErrorCode.OCR_NO_TEXT_FOUND: "No text could be extracted from the document",

    ErrorCode.BATCH_SIZE_EXCEEDED: "Batch size exceeds the maximum limit of 20 documents",
    ErrorCode.BATCH_TIMEOUT: "Batch processing timed out",
    ErrorCode.BATCH_PARTIAL_FAILURE: "Some documents in the batch failed to process",

    ErrorCode.HISTORY_NOT_FOUND: "No processing history found for this document",
    ErrorCode.HISTORY_EXPIRED: "Processing history has expired (retention period: 7 days)",
    ErrorCode.HISTORY_DATABASE_ERROR: "Error accessing processing history database",

    ErrorCode.INVALID_REQUEST: "Invalid request format or parameters",
    ErrorCode.INVALID_BASE64: "Invalid base64 encoded data",
    ErrorCode.TIMEOUT: "Request processing timed out",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred while processing the request",
    ErrorCode.SERVICE_UNAVAILABLE: "The service is temporarily unavailable",
    ErrorCode.AUTHENTICATION_FAILED: "Authentication failed",
    ErrorCode.PERMISSION_DENIED: "Permission denied for this operation"
}


# HTTP status code mapping
ERROR_STATUS_CODES: Dict[ErrorCode, int] = {
    # 400 Bad Request
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.INVALID_BASE64: 400,
    ErrorCode.DIMENSIONS_INVALID: 400,
    ErrorCode.DIMENSIONS_TOO_SMALL: 400,
    ErrorCode.DIMENSIONS_TOO_LARGE: 400,
    ErrorCode.IMAGE_QUALITY_TOO_LOW: 400,
    ErrorCode.IMAGE_COVERAGE_INSUFFICIENT: 400,
    ErrorCode.BATCH_SIZE_EXCEEDED: 400,
    ErrorCode.PDF_PAGE_NOT_FOUND: 400,

    # 401 Unauthorized
    ErrorCode.AUTHENTICATION_FAILED: 401,

    # 403 Forbidden
    ErrorCode.PERMISSION_DENIED: 403,

    # 404 Not Found
    ErrorCode.HISTORY_NOT_FOUND: 404,
    ErrorCode.HISTORY_EXPIRED: 404,

    # 408 Request Timeout
    ErrorCode.TIMEOUT: 408,
    ErrorCode.OCR_TIMEOUT: 408,
    ErrorCode.BATCH_TIMEOUT: 408,

    # 413 Payload Too Large
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.PDF_TOO_MANY_PAGES: 413,

    # 415 Unsupported Media Type
    ErrorCode.FORMAT_NOT_SUPPORTED: 415,
    ErrorCode.FORMAT_DETECTION_FAILED: 415,

    # 422 Unprocessable Entity
    ErrorCode.FILE_EMPTY: 422,
    ErrorCode.PDF_EMPTY: 422,
    ErrorCode.IMAGE_CORRUPTED: 422,
    ErrorCode.PDF_CORRUPTED: 422,

    # 500 Internal Server Error
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.FORMAT_CONVERSION_FAILED: 500,
    ErrorCode.OCR_FAILED: 500,
    ErrorCode.PDF_PAGE_EXTRACTION_FAILED: 500,
    ErrorCode.HISTORY_DATABASE_ERROR: 500,

    # 503 Service Unavailable
    ErrorCode.SERVICE_UNAVAILABLE: 503,

    # 207 Multi-Status (for partial success)
    ErrorCode.BATCH_PARTIAL_FAILURE: 207,
}


class ProcessingError(Exception):
    """
    Custom exception for document processing errors
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message or ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}
        self.status_code = ERROR_STATUS_CODES.get(error_code, 500)
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API response"""
        return {
            "error_code": self.error_code.value,
            "error": self.message,
            "details": self.details
        }

    def to_response(self) -> tuple[Dict[str, Any], int]:
        """Convert to API response format with status code"""
        return self.to_dict(), self.status_code


def create_error_response(
    error_code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> tuple[Dict[str, Any], int]:
    """
    Create standardized error response
    Returns: (response_dict, status_code)
    """
    error = ProcessingError(error_code, message, details)
    return error.to_response()