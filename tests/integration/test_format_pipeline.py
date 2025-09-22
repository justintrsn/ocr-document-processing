"""
Integration tests for format detection and conversion pipeline
Tests the complete flow from format detection to PIL Image conversion
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import base64
import io
from PIL import Image
import struct


@pytest.fixture
def format_samples():
    """Create sample files for each format with correct magic bytes"""
    samples = {}

    # PNG
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    samples['PNG'] = buffer.getvalue()

    # JPEG
    img = Image.new('RGB', (100, 100), color='green')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    samples['JPG'] = buffer.getvalue()

    # BMP
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='BMP')
    samples['BMP'] = buffer.getvalue()

    # GIF
    img = Image.new('P', (100, 100), color=0)
    buffer = io.BytesIO()
    img.save(buffer, format='GIF')
    samples['GIF'] = buffer.getvalue()

    # TIFF
    img = Image.new('RGB', (100, 100), color='yellow')
    buffer = io.BytesIO()
    img.save(buffer, format='TIFF')
    samples['TIFF'] = buffer.getvalue()

    # WebP
    img = Image.new('RGB', (100, 100), color='cyan')
    buffer = io.BytesIO()
    img.save(buffer, format='WebP')
    samples['WebP'] = buffer.getvalue()

    # ICO
    img = Image.new('RGB', (32, 32), color='magenta')
    buffer = io.BytesIO()
    img.save(buffer, format='ICO')
    samples['ICO'] = buffer.getvalue()

    # PDF (minimal valid PDF)
    samples['PDF'] = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"

    # PSD mock (PSD files have complex structure, using magic bytes only)
    samples['PSD'] = b"8BPS\x00\x01" + b"\x00" * 100  # Simplified PSD header

    # PCX
    samples['PCX'] = b"\x0A\x05\x01\x08" + b"\x00" * 100  # PCX header

    return samples


class TestFormatDetectionPipeline:
    """Test format detection and validation"""

    def test_magic_byte_detection_all_formats(self, format_samples):
        """Test magic byte detection for each format"""
        from src.services.format_detector import FormatDetector

        detector = FormatDetector()

        expected_formats = {
            'PNG': 'PNG',
            'JPG': 'JPG',
            'BMP': 'BMP',
            'GIF': 'GIF',
            'TIFF': 'TIFF',
            'WebP': 'WebP',
            'ICO': 'ICO',
            'PDF': 'PDF',
            'PSD': 'PSD',
            'PCX': 'PCX'
        }

        for format_name, file_bytes in format_samples.items():
            detected = detector.detect_format(file_bytes)
            assert detected == expected_formats.get(format_name, format_name), \
                f"Failed to detect {format_name}"

    def test_format_detection_with_corrupted_header(self):
        """Test format detection with corrupted file headers"""
        from src.services.format_detector import FormatDetector

        detector = FormatDetector()

        # Corrupted/unknown format
        corrupted = b"\xFF\xFF\xFF\xFF" + b"\x00" * 100

        detected = detector.detect_format(corrupted)
        assert detected == "UNKNOWN" or detected is None

    def test_format_validation_after_detection(self, format_samples):
        """Test that detected formats pass validation"""
        from src.services.format_detector import FormatDetector
        from src.core.validators.format_validator import FormatValidator

        detector = FormatDetector()
        validator = FormatValidator()

        for format_name, file_bytes in format_samples.items():
            # Skip mock formats that might not validate
            if format_name in ['PSD', 'PCX']:
                continue

            detected = detector.detect_format(file_bytes)

            # Validate the detected format
            is_valid = validator.validate_format(
                file_bytes=file_bytes,
                detected_format=detected
            )

            assert is_valid, f"Format {format_name} failed validation"


class TestFormatConversionPipeline:
    """Test format conversion to PIL Image"""

    def test_image_format_conversion(self, format_samples):
        """Test conversion of standard image formats to PIL"""
        from src.core.converters.image_converter import ImageFormatConverter

        converter = ImageFormatConverter()

        # Test formats that PIL handles natively
        native_formats = ['PNG', 'JPG', 'BMP', 'GIF', 'TIFF', 'WebP', 'ICO']

        for format_name in native_formats:
            if format_name in format_samples:
                file_bytes = format_samples[format_name]

                pil_image = converter.convert_to_pil(file_bytes)

                assert isinstance(pil_image, Image.Image)
                assert pil_image.size == (100, 100) or pil_image.size == (32, 32)  # ICO is 32x32

    def test_psd_format_conversion(self):
        """Test PSD to PIL conversion using psd-tools"""
        from src.core.converters.psd_converter import PSDFormatConverter
        import psd_tools

        converter = PSDFormatConverter()

        # Create a mock PSD that psd-tools can handle
        with patch('psd_tools.PSDImage.open') as mock_open:
            mock_psd = MagicMock()
            mock_composite = Image.new('RGB', (100, 100), color='purple')
            mock_psd.composite.return_value = mock_composite
            mock_open.return_value = mock_psd

            psd_bytes = b"8BPS" + b"\x00" * 100  # Fake PSD data

            pil_image = converter.convert_to_pil(psd_bytes)

            assert isinstance(pil_image, Image.Image)
            assert pil_image.size == (100, 100)
            mock_psd.composite.assert_called_once()

    def test_pdf_page_extraction_conversion(self):
        """Test PDF page extraction and conversion to PIL"""
        from src.core.converters.pdf_converter import PDFFormatConverter

        converter = PDFFormatConverter()

        # Mock pdf2image
        with patch('pdf2image.convert_from_bytes') as mock_convert:
            mock_pages = [
                Image.new('RGB', (612, 792), color='white'),
                Image.new('RGB', (612, 792), color='gray'),
                Image.new('RGB', (612, 792), color='black')
            ]
            mock_convert.return_value = mock_pages

            pdf_bytes = b"%PDF-1.4" + b"\x00" * 100

            # Extract specific page
            page_image = converter.extract_page(pdf_bytes, page_number=2)

            assert isinstance(page_image, Image.Image)
            assert page_image.size == (612, 792)

            # Get page count
            count = converter.get_page_count(pdf_bytes)
            assert count == 3

    def test_pcx_format_conversion(self):
        """Test PCX format conversion"""
        from src.core.converters.pcx_converter import PCXFormatConverter

        converter = PCXFormatConverter()

        # Create a valid PCX file
        img = Image.new('RGB', (100, 100), color='orange')
        buffer = io.BytesIO()
        img.save(buffer, format='PCX')
        pcx_bytes = buffer.getvalue()

        pil_image = converter.convert_to_pil(pcx_bytes)

        assert isinstance(pil_image, Image.Image)
        assert pil_image.size == (100, 100)


class TestDimensionValidation:
    """Test dimension validation after conversion"""

    def test_dimension_validation_valid(self):
        """Test validation passes for valid dimensions (15-30000px)"""
        from src.core.validators.format_validator import FormatValidator

        validator = FormatValidator()

        # Valid dimension image
        img = Image.new('RGB', (1000, 1000), color='white')

        is_valid = validator.validate_dimensions(img)
        assert is_valid

    def test_dimension_validation_too_small(self):
        """Test validation fails for dimensions < 15px"""
        from src.core.validators.format_validator import FormatValidator

        validator = FormatValidator()

        # Too small
        img = Image.new('RGB', (10, 10), color='white')

        is_valid = validator.validate_dimensions(img)
        assert not is_valid

    def test_dimension_validation_too_large(self):
        """Test validation fails for dimensions > 30000px"""
        from src.core.validators.format_validator import FormatValidator

        validator = FormatValidator()

        # Too large
        img = Image.new('RGB', (35000, 35000), color='white')

        is_valid = validator.validate_dimensions(img)
        assert not is_valid


class TestAutoRotation:
    """Test auto-rotation detection and correction"""

    def test_auto_rotation_detection(self):
        """Test detection of image rotation"""
        from src.core.converters.base_converter import BaseFormatConverter

        converter = BaseFormatConverter()

        # Create rotated image
        img = Image.new('RGB', (100, 200), color='white')

        # Add text-like features that are rotated
        # In real implementation, this would use OpenCV

        with patch('cv2.minAreaRect') as mock_rect:
            # Mock detected rotation angle
            mock_rect.return_value = (None, None, -15)  # 15 degrees rotation

            rotation_angle = converter.detect_rotation(img)

            assert rotation_angle == -15

    def test_auto_rotation_correction(self):
        """Test automatic rotation correction"""
        from src.core.converters.base_converter import BaseFormatConverter

        converter = BaseFormatConverter()

        # Create image
        img = Image.new('RGB', (100, 200), color='white')

        with patch.object(converter, 'detect_rotation') as mock_detect:
            mock_detect.return_value = 90  # 90 degrees rotation needed

            rotated_img = converter.auto_rotate(img)

            # After 90 degree rotation, dimensions should swap
            assert rotated_img.size == (200, 100)


class TestSizeValidation:
    """Test file size validation"""

    def test_size_validation_valid(self):
        """Test validation passes for files <= 10MB"""
        from src.core.validators.format_validator import FormatValidator

        validator = FormatValidator()

        # 5MB file
        file_bytes = b"x" * (5 * 1024 * 1024)

        is_valid = validator.validate_size(file_bytes)
        assert is_valid

    def test_size_validation_too_large(self):
        """Test validation fails for files > 10MB"""
        from src.core.validators.format_validator import FormatValidator

        validator = FormatValidator()

        # 11MB file
        file_bytes = b"x" * (11 * 1024 * 1024)

        is_valid = validator.validate_size(file_bytes)
        assert not is_valid


class TestFormatAdapterService:
    """Test the format adapter service that orchestrates the pipeline"""

    def test_complete_pipeline_flow(self, format_samples):
        """Test complete flow from raw bytes to PIL Image"""
        from src.services.format_adapter import FormatAdapterService

        adapter = FormatAdapterService()

        for format_name in ['PNG', 'JPG', 'BMP', 'GIF']:
            if format_name in format_samples:
                file_bytes = format_samples[format_name]

                result = adapter.process_document(
                    file_bytes=file_bytes,
                    auto_rotate=True,
                    validate_dimensions=True
                )

                assert result["status"] == "success"
                assert "image" in result
                assert isinstance(result["image"], Image.Image)
                assert "format_detected" in result
                assert result["format_detected"] == format_name
                assert "metadata" in result

    def test_pipeline_with_unsupported_format(self):
        """Test pipeline handling of unsupported format"""
        from src.services.format_adapter import FormatAdapterService

        adapter = FormatAdapterService()

        # Unsupported format
        unsupported_bytes = b"\x00\x00\x00\x00" + b"INVALID"

        result = adapter.process_document(file_bytes=unsupported_bytes)

        assert result["status"] == "error"
        assert result["error_code"] == "FORMAT_NOT_SUPPORTED"

    def test_pipeline_error_handling(self):
        """Test pipeline error handling and recovery"""
        from src.services.format_adapter import FormatAdapterService

        adapter = FormatAdapterService()

        # Corrupted PNG header but valid magic bytes
        corrupted_png = b"\x89PNG\r\n\x1a\n" + b"CORRUPTED_DATA"

        result = adapter.process_document(file_bytes=corrupted_png)

        assert result["status"] == "error"
        assert "error_code" in result
        assert "error" in result