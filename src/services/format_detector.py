"""
Format detection service for identifying document types
"""

import logging
from typing import Optional, Tuple, Dict, Any
from src.models.formats import FileFormat, SUPPORTED_FORMATS, get_format_by_magic_bytes

logger = logging.getLogger(__name__)


class FormatDetector:
    """
    Detects file format using magic bytes and other heuristics
    """

    # Define magic bytes for each format
    MAGIC_BYTES = {
        b'\x89PNG\r\n\x1a\n': FileFormat.PNG,
        b'\xff\xd8\xff': FileFormat.JPG,  # Also covers JPEG
        b'BM': FileFormat.BMP,
        b'GIF87a': FileFormat.GIF,
        b'GIF89a': FileFormat.GIF,
        b'II\x2a\x00': FileFormat.TIFF,  # Little-endian TIFF
        b'MM\x00\x2a': FileFormat.TIFF,  # Big-endian TIFF
        b'RIFF': FileFormat.WEBP,  # WebP starts with RIFF
        b'\x00\x00\x01\x00': FileFormat.ICO,
        b'\x00\x00\x02\x00': FileFormat.ICO,  # CUR format (cursor)
        b'8BPS': FileFormat.PSD,
        b'%PDF': FileFormat.PDF,
        b'\x0a\x05\x01\x08': FileFormat.PCX,
        b'\x0a\x02\x01\x08': FileFormat.PCX,
        b'\x0a\x03\x01\x08': FileFormat.PCX,
        b'\x0a\x04\x01\x08': FileFormat.PCX,
        b'\x0a\x05\x01\x01': FileFormat.PCX,
    }

    # Alternative magic bytes for some formats
    ALTERNATIVE_MAGIC = {
        # JPEG variants
        b'\xff\xd8\xff\xe0': FileFormat.JPG,  # JPEG with JFIF
        b'\xff\xd8\xff\xe1': FileFormat.JPG,  # JPEG with EXIF
        b'\xff\xd8\xff\xe2': FileFormat.JPG,  # JPEG with ICC
        b'\xff\xd8\xff\xe8': FileFormat.JPG,  # JPEG with SPIFF
        b'\xff\xd8\xff\xdb': FileFormat.JPG,  # JPEG with DQT
        # PCX variants (different versions)
        b'\x0a\x00': FileFormat.PCX,  # Version 0
        b'\x0a\x02': FileFormat.PCX,  # Version 2
        b'\x0a\x03': FileFormat.PCX,  # Version 3
        b'\x0a\x04': FileFormat.PCX,  # Version 4
        b'\x0a\x05': FileFormat.PCX,  # Version 5
    }

    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS

    def detect_format(self, file_bytes: bytes) -> Optional[str]:
        """
        Detect format from file bytes
        Returns format name or None if not detected
        """
        if not file_bytes or len(file_bytes) < 4:
            logger.warning("File too small for format detection")
            return None

        # Try exact magic bytes first
        format_type = self._check_magic_bytes(file_bytes)

        if format_type:
            format_name = format_type.value
            logger.debug(f"Detected format: {format_name} via magic bytes")
            return format_name

        # Try alternative detection methods
        format_type = self._check_alternative_detection(file_bytes)

        if format_type:
            format_name = format_type.value
            logger.debug(f"Detected format: {format_name} via alternative method")
            return format_name

        logger.warning("Could not detect file format")
        return None

    def _check_magic_bytes(self, file_bytes: bytes) -> Optional[FileFormat]:
        """
        Check against known magic bytes
        """
        # Check main magic bytes
        for magic, format_type in self.MAGIC_BYTES.items():
            if file_bytes.startswith(magic):
                # Special handling for WebP
                if magic == b'RIFF' and len(file_bytes) > 12:
                    # Check for WebP signature
                    if file_bytes[8:12] == b'WEBP':
                        return FileFormat.WEBP
                    else:
                        continue  # Not WebP, skip
                return format_type

        # Check alternative magic bytes
        for magic, format_type in self.ALTERNATIVE_MAGIC.items():
            if file_bytes.startswith(magic):
                return format_type

        return None

    def _check_alternative_detection(self, file_bytes: bytes) -> Optional[FileFormat]:
        """
        Try alternative detection methods for formats
        that don't have clear magic bytes
        """
        # Check for JPEG by looking for SOI and EOI markers
        if len(file_bytes) > 4:
            if file_bytes[0:2] == b'\xff\xd8' and b'\xff\xd9' in file_bytes[-20:]:
                return FileFormat.JPG

        # Check for PDF with whitespace
        if len(file_bytes) > 10:
            header = file_bytes[:10].strip()
            if header.startswith(b'%PDF'):
                return FileFormat.PDF

        # Check for PCX by first byte only
        if len(file_bytes) > 1 and file_bytes[0] == 0x0A:
            return FileFormat.PCX

        return None

    def detect_with_metadata(
        self,
        file_bytes: bytes,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Detect format using multiple sources of information
        Returns: (format_name, metadata)
        """
        metadata = {
            'detection_method': None,
            'confidence': 0.0,
            'file_size': len(file_bytes)
        }

        # Try magic bytes detection first (highest confidence)
        format_name = self.detect_format(file_bytes)
        if format_name:
            metadata['detection_method'] = 'magic_bytes'
            metadata['confidence'] = 0.95
            return format_name, metadata

        # Try filename extension (medium confidence)
        if filename:
            format_name = self._detect_from_filename(filename)
            if format_name:
                metadata['detection_method'] = 'filename_extension'
                metadata['confidence'] = 0.7
                return format_name, metadata

        # Try MIME type (low confidence)
        if mime_type:
            format_name = self._detect_from_mime(mime_type)
            if format_name:
                metadata['detection_method'] = 'mime_type'
                metadata['confidence'] = 0.6
                return format_name, metadata

        metadata['detection_method'] = 'failed'
        metadata['confidence'] = 0.0
        return None, metadata

    def _detect_from_filename(self, filename: str) -> Optional[str]:
        """
        Detect format from filename extension
        """
        if '.' not in filename:
            return None

        extension = filename.rsplit('.', 1)[-1].upper()

        # Map extensions to formats
        extension_map = {
            'PNG': FileFormat.PNG,
            'JPG': FileFormat.JPG,
            'JPEG': FileFormat.JPEG,
            'BMP': FileFormat.BMP,
            'GIF': FileFormat.GIF,
            'TIF': FileFormat.TIFF,
            'TIFF': FileFormat.TIFF,
            'WEBP': FileFormat.WEBP,
            'ICO': FileFormat.ICO,
            'PSD': FileFormat.PSD,
            'PDF': FileFormat.PDF,
            'PCX': FileFormat.PCX,
        }

        format_type = extension_map.get(extension)
        if format_type:
            return format_type.value

        return None

    def _detect_from_mime(self, mime_type: str) -> Optional[str]:
        """
        Detect format from MIME type
        """
        mime_map = {
            'image/png': FileFormat.PNG,
            'image/jpeg': FileFormat.JPG,
            'image/jpg': FileFormat.JPG,
            'image/bmp': FileFormat.BMP,
            'image/x-ms-bmp': FileFormat.BMP,
            'image/gif': FileFormat.GIF,
            'image/tiff': FileFormat.TIFF,
            'image/webp': FileFormat.WEBP,
            'image/x-icon': FileFormat.ICO,
            'image/vnd.microsoft.icon': FileFormat.ICO,
            'image/vnd.adobe.photoshop': FileFormat.PSD,
            'application/pdf': FileFormat.PDF,
            'image/x-pcx': FileFormat.PCX,
            'image/pcx': FileFormat.PCX,
        }

        format_type = mime_map.get(mime_type.lower())
        if format_type:
            return format_type.value

        return None

    def validate_format(
        self,
        file_bytes: bytes,
        expected_format: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that file matches expected format
        Returns: (is_valid, error_message)
        """
        detected_format = self.detect_format(file_bytes)

        if not detected_format:
            return False, "Could not detect file format"

        # Handle JPEG/JPG equivalence
        if expected_format.upper() in ['JPEG', 'JPG'] and detected_format in ['JPEG', 'JPG']:
            return True, None

        if detected_format.upper() != expected_format.upper():
            return False, f"Expected {expected_format}, but detected {detected_format}"

        return True, None

    def get_format_info(self, format_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a format
        """
        try:
            format_enum = FileFormat(format_name.upper())
            format_def = self.supported_formats.get(format_enum)

            if format_def:
                return {
                    'name': format_def.format_name,
                    'extensions': format_def.extensions,
                    'mime_types': format_def.mime_types,
                    'max_size_mb': format_def.max_size_mb,
                    'min_dimension': format_def.min_dimension,
                    'max_dimension': format_def.max_dimension,
                    'supports_multi_page': format_def.supports_multi_page,
                    'requires_special_converter': format_def.requires_special_converter
                }
        except ValueError:
            pass

        return {'error': f"Unknown format: {format_name}"}

    def is_format_supported(self, format_name: str) -> bool:
        """
        Check if a format is supported
        """
        try:
            FileFormat(format_name.upper())
            return True
        except ValueError:
            return False

    def get_supported_formats(self) -> list[str]:
        """
        Get list of all supported formats
        """
        return [f.value for f in FileFormat]


# Alias for backward compatibility
FormatDetectionService = FormatDetector