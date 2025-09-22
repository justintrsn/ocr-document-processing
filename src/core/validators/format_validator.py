"""
Format validation logic for document processing
"""

from typing import Optional, Tuple, Dict, Any
from PIL import Image
import io
import base64
from src.models.formats import SUPPORTED_FORMATS, FileFormat, SupportedFormat, get_format_by_magic_bytes
from src.core.config import settings


class ValidationError(Exception):
    """Base validation error"""
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class FormatValidator:
    """
    Validates file formats against defined constraints
    """

    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS
        self.max_size_mb = settings.image_max_size_mb
        self.min_dimension = 15
        self.max_dimension = 30000

    def validate_magic_bytes(self, file_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate file format using magic bytes
        Returns: (is_valid, detected_format)
        """
        detected_format = get_format_by_magic_bytes(file_bytes)
        if detected_format:
            return True, detected_format.format_name
        return False, None

    def validate_dimensions(self, image: Image.Image) -> bool:
        """Validate image dimensions"""
        width, height = image.size
        return (
            self.min_dimension <= width <= self.max_dimension and
            self.min_dimension <= height <= self.max_dimension
        )

    def validate_size(self, file_bytes: bytes) -> bool:
        """Validate file size"""
        size_bytes = len(file_bytes)
        max_bytes = self.max_size_mb * 1024 * 1024
        return size_bytes <= max_bytes

    def validate_coverage(self, image: Image.Image, min_coverage: float = 0.8) -> bool:
        """
        Validate image coverage (non-white space)
        Ensures at least 80% of image contains content
        """
        # Convert to grayscale for analysis
        gray = image.convert('L')
        pixels = gray.getdata()

        # Count non-white pixels (assuming white is > 250)
        non_white = sum(1 for pixel in pixels if pixel < 250)
        total_pixels = len(pixels)

        coverage = non_white / total_pixels if total_pixels > 0 else 0
        return coverage >= min_coverage

    def validate_format(
        self,
        file_bytes: bytes,
        detected_format: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Complete format validation
        Returns: (is_valid, format_name, error_message)
        """
        # Check size first (fastest)
        if not self.validate_size(file_bytes):
            return False, None, "FILE_TOO_LARGE"

        # Detect format from magic bytes
        is_valid, format_name = self.validate_magic_bytes(file_bytes)
        if not is_valid:
            return False, None, "FORMAT_NOT_SUPPORTED"

        # Override with hint if provided and matches
        if detected_format and detected_format.upper() in FileFormat.__members__:
            format_name = detected_format.upper()

        return True, format_name, None

    def validate_base64(self, base64_string: str) -> Tuple[bool, bytes, Optional[str]]:
        """
        Validate and decode base64 string
        Returns: (is_valid, decoded_bytes, error_message)
        """
        try:
            # Remove data URI prefix if present
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            decoded = base64.b64decode(base64_string)
            return True, decoded, None
        except Exception as e:
            return False, b"", f"Invalid base64: {str(e)}"


class ImageFormatValidator(FormatValidator):
    """Specific validator for image formats"""

    def validate_image(
        self,
        file_bytes: bytes,
        format_hint: Optional[str] = None
    ) -> Tuple[bool, Optional[Image.Image], Optional[str]]:
        """
        Validate image file and return PIL Image
        Returns: (is_valid, image, error_code)
        """
        # Basic format validation
        is_valid, format_name, error = self.validate_format(file_bytes, format_hint)
        if not is_valid:
            return False, None, error

        # Try to open as image
        try:
            image = Image.open(io.BytesIO(file_bytes))

            # Validate dimensions
            if not self.validate_dimensions(image):
                width, height = image.size
                return False, None, f"DIMENSIONS_INVALID: {width}x{height}"

            return True, image, None

        except Exception as e:
            return False, None, f"IMAGE_CORRUPT: {str(e)}"


class PDFFormatValidator(FormatValidator):
    """Specific validator for PDF format"""

    def validate_pdf(
        self,
        file_bytes: bytes
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validate PDF file and return page count
        Returns: (is_valid, page_count, error_code)
        """
        # Check magic bytes
        if not file_bytes.startswith(b"%PDF"):
            return False, None, "NOT_A_PDF"

        # Basic size validation
        if not self.validate_size(file_bytes):
            return False, None, "FILE_TOO_LARGE"

        # Try to get page count (requires pdf2image)
        try:
            from pdf2image import pdfinfo_from_bytes
            info = pdfinfo_from_bytes(file_bytes)
            page_count = info.get("Pages", 0)

            if page_count == 0:
                return False, None, "PDF_EMPTY"

            if page_count > settings.pdf_max_pages_auto_process:
                return False, None, f"PDF_TOO_MANY_PAGES: {page_count}"

            return True, page_count, None

        except Exception as e:
            # If we can't parse it, it might be corrupted
            return False, None, f"PDF_CORRUPT: {str(e)}"


class PSDFormatValidator(FormatValidator):
    """Specific validator for PSD format"""

    def validate_psd(
        self,
        file_bytes: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate PSD file and return metadata
        Returns: (is_valid, metadata, error_code)
        """
        # Check magic bytes
        if not file_bytes.startswith(b"8BPS"):
            return False, None, "NOT_A_PSD"

        # Basic size validation
        if not self.validate_size(file_bytes):
            return False, None, "FILE_TOO_LARGE"

        # Try to read PSD header (requires psd-tools)
        try:
            from psd_tools import PSDImage
            psd = PSDImage.open(io.BytesIO(file_bytes))

            metadata = {
                "width": psd.width,
                "height": psd.height,
                "channels": psd.channels,
                "depth": psd.depth,
                "color_mode": str(psd.color_mode)
            }

            # Validate dimensions
            if not (self.min_dimension <= psd.width <= self.max_dimension and
                    self.min_dimension <= psd.height <= self.max_dimension):
                return False, None, f"DIMENSIONS_INVALID: {psd.width}x{psd.height}"

            return True, metadata, None

        except Exception as e:
            return False, None, f"PSD_CORRUPT: {str(e)}"


def get_validator_for_format(format_name: str) -> FormatValidator:
    """Get appropriate validator for a format"""
    format_upper = format_name.upper()

    if format_upper == "PDF":
        return PDFFormatValidator()
    elif format_upper == "PSD":
        return PSDFormatValidator()
    elif format_upper in ["PNG", "JPG", "JPEG", "BMP", "GIF", "TIFF", "WEBP", "PCX", "ICO"]:
        return ImageFormatValidator()
    else:
        return FormatValidator()