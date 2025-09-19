"""
Unit tests for Image Quality Service
"""

import pytest
from pathlib import Path
import numpy as np
from PIL import Image
import io

from src.services.image_quality_service import ImageQualityAssessor


class TestImageQualityAssessor:
    """Test image quality assessment functions"""

    @pytest.fixture
    def service(self):
        return ImageQualityAssessor()

    @pytest.fixture
    def test_image_path(self):
        """Path to test image"""
        path = Path("tests/documents/scanned_document.jpg")
        if path.exists():
            return path
        # Create a simple test image if document doesn't exist
        img = Image.new('RGB', (800, 600), color='white')
        test_path = Path("tests/test_image.jpg")
        test_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(test_path)
        return test_path

    def test_assess_with_path(self, service, test_image_path):
        """Test assessment with file path"""
        result = service.assess(image_path=test_image_path)

        assert result is not None
        assert 0 <= result.overall_score <= 100
        assert 0 <= result.sharpness_score <= 100
        assert 0 <= result.contrast_score <= 100
        assert 0 <= result.resolution_score <= 100
        assert 0 <= result.noise_score <= 100
        assert isinstance(result.issues, list)

    def test_assess_with_bytes(self, service, test_image_path):
        """Test assessment with raw bytes"""
        with open(test_image_path, 'rb') as f:
            image_bytes = f.read()

        result = service.assess(image_data=image_bytes)

        assert result is not None
        assert 0 <= result.overall_score <= 100

    def test_quality_thresholds(self, service):
        """Test quality score thresholds"""
        # Create a high-quality test image
        high_quality = Image.new('RGB', (1920, 1080), color='white')

        # Add some contrast
        pixels = high_quality.load()
        for i in range(0, 1920, 10):
            for j in range(0, 1080, 10):
                pixels[i, j] = (0, 0, 0)

        # Save to bytes
        img_bytes = io.BytesIO()
        high_quality.save(img_bytes, format='JPEG', quality=95)
        img_bytes.seek(0)

        result = service.assess(image_data=img_bytes.read())

        # High-quality image should have good scores
        assert result.resolution_score > 50, "Resolution score should be good for HD image"
        assert result.contrast_score > 30, "Should have some contrast"

    def test_low_quality_detection(self, service):
        """Test detection of low-quality images"""
        # Create a low-quality test image
        low_quality = Image.new('RGB', (100, 100), color='gray')

        img_bytes = io.BytesIO()
        low_quality.save(img_bytes, format='JPEG', quality=30)
        img_bytes.seek(0)

        result = service.assess(image_data=img_bytes.read())

        # Low-quality image should have lower scores
        assert result.resolution_score < 50, "Low resolution should be detected"
        assert len(result.issues) > 0, "Should detect quality issues"

    def test_error_handling(self, service):
        """Test error handling for invalid inputs"""
        # Test with non-existent file
        result = service.assess(image_path=Path("non_existent.jpg"))
        assert result is None

        # Test with invalid bytes
        result = service.assess(image_data=b"invalid image data")
        assert result is None

        # Test with no input
        result = service.assess()
        assert result is None