"""
Supported format definitions for document processing
"""

from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class FileFormat(str, Enum):
    """Supported file formats"""
    PNG = "PNG"
    JPG = "JPG"
    JPEG = "JPEG"
    BMP = "BMP"
    GIF = "GIF"
    TIFF = "TIFF"
    WEBP = "WebP"
    PCX = "PCX"
    ICO = "ICO"
    PSD = "PSD"
    PDF = "PDF"


@dataclass
class SupportedFormat:
    """
    Definition of a supported file format with constraints and metadata
    """
    format_name: str
    extensions: List[str]
    mime_types: List[str]
    magic_bytes: bytes
    max_size_mb: float = 10.0
    min_dimension: int = 15
    max_dimension: int = 30000
    supports_multi_page: bool = False
    requires_special_converter: bool = False

    def validate_size(self, file_size_bytes: int) -> bool:
        """Validate file size against format constraints"""
        return file_size_bytes <= (self.max_size_mb * 1024 * 1024)

    def validate_dimensions(self, width: int, height: int) -> bool:
        """Validate image dimensions against format constraints"""
        return (
            self.min_dimension <= width <= self.max_dimension and
            self.min_dimension <= height <= self.max_dimension
        )

    def matches_magic_bytes(self, file_bytes: bytes) -> bool:
        """Check if file bytes match this format's magic bytes"""
        if not self.magic_bytes:
            return False
        return file_bytes.startswith(self.magic_bytes)


# Define all supported formats
SUPPORTED_FORMATS = {
    FileFormat.PNG: SupportedFormat(
        format_name="PNG",
        extensions=[".png"],
        mime_types=["image/png"],
        magic_bytes=b"\x89PNG\r\n\x1a\n"
    ),
    FileFormat.JPG: SupportedFormat(
        format_name="JPG",
        extensions=[".jpg", ".jpeg"],
        mime_types=["image/jpeg"],
        magic_bytes=b"\xff\xd8\xff"
    ),
    FileFormat.JPEG: SupportedFormat(
        format_name="JPEG",
        extensions=[".jpeg", ".jpg"],
        mime_types=["image/jpeg"],
        magic_bytes=b"\xff\xd8\xff"
    ),
    FileFormat.BMP: SupportedFormat(
        format_name="BMP",
        extensions=[".bmp"],
        mime_types=["image/bmp", "image/x-ms-bmp"],
        magic_bytes=b"BM"
    ),
    FileFormat.GIF: SupportedFormat(
        format_name="GIF",
        extensions=[".gif"],
        mime_types=["image/gif"],
        magic_bytes=b"GIF"
    ),
    FileFormat.TIFF: SupportedFormat(
        format_name="TIFF",
        extensions=[".tiff", ".tif"],
        mime_types=["image/tiff"],
        magic_bytes=b"II\x2a\x00"  # Little-endian TIFF
    ),
    FileFormat.WEBP: SupportedFormat(
        format_name="WebP",
        extensions=[".webp"],
        mime_types=["image/webp"],
        magic_bytes=b"RIFF"  # WebP starts with RIFF
    ),
    FileFormat.PCX: SupportedFormat(
        format_name="PCX",
        extensions=[".pcx"],
        mime_types=["image/x-pcx", "image/pcx"],
        magic_bytes=b"\x0a\x05\x01\x08"
    ),
    FileFormat.ICO: SupportedFormat(
        format_name="ICO",
        extensions=[".ico"],
        mime_types=["image/x-icon", "image/vnd.microsoft.icon"],
        magic_bytes=b"\x00\x00\x01\x00"
    ),
    FileFormat.PSD: SupportedFormat(
        format_name="PSD",
        extensions=[".psd"],
        mime_types=["image/vnd.adobe.photoshop"],
        magic_bytes=b"8BPS",
        requires_special_converter=True
    ),
    FileFormat.PDF: SupportedFormat(
        format_name="PDF",
        extensions=[".pdf"],
        mime_types=["application/pdf"],
        magic_bytes=b"%PDF",
        supports_multi_page=True,
        requires_special_converter=True
    )
}


def get_format_by_extension(extension: str) -> Optional[SupportedFormat]:
    """Get format definition by file extension"""
    ext_lower = extension.lower()
    if not ext_lower.startswith('.'):
        ext_lower = f".{ext_lower}"

    for format_def in SUPPORTED_FORMATS.values():
        if ext_lower in format_def.extensions:
            return format_def
    return None


def get_format_by_magic_bytes(file_bytes: bytes) -> Optional[SupportedFormat]:
    """Detect format by magic bytes"""
    # Check special cases first
    if file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:20]:
        return SUPPORTED_FORMATS[FileFormat.WEBP]

    # Check each format
    for format_def in SUPPORTED_FORMATS.values():
        if format_def.matches_magic_bytes(file_bytes):
            return format_def

    return None


def is_format_supported(format_name: str) -> bool:
    """Check if a format name is supported"""
    try:
        FileFormat(format_name.upper())
        return True
    except ValueError:
        return False