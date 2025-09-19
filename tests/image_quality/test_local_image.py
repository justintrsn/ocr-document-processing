"""
Test image quality assessment for local files
"""

import pytest
from pathlib import Path

from src.models.quality import QualityAssessment


class TestLocalImageQuality:
    """Test image quality assessment for local files"""

    def test_assess_from_local_file(self, assessor, test_image_path):
        """Test assessment from actual local file path."""
        if test_image_path.exists():
            assessment = assessor.assess(image_path=test_image_path)
            assert isinstance(assessment, QualityAssessment)
            assert assessment.overall_score > 0
            assert assessment.sharpness_score >= 0
            assert assessment.contrast_score >= 0
            assert assessment.resolution_score >= 0
            assert assessment.noise_score >= 0

    def test_assess_from_temp_file(self, assessor, temp_image_file):
        """Test assessment from temporary file."""
        assessment = assessor.assess(image_path=temp_image_file)

        assert isinstance(assessment, QualityAssessment)
        assert assessment.sharpness_score > 70  # Sharp image should score well
        assert assessment.overall_score > 60

    def test_assess_sharp_local_image(self, assessor, sharp_image):
        """Test assessment of sharp image from local file."""
        # Create temp file
        from tempfile import NamedTemporaryFile
        import os

        with NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(sharp_image)
            temp_path = Path(f.name)

        try:
            assessment = assessor.assess(image_path=temp_path)
            assert isinstance(assessment, QualityAssessment)
            assert assessment.sharpness_score > 70
            assert assessment.overall_score > 60
        finally:
            os.unlink(temp_path)

    def test_assess_blurry_local_image(self, assessor, blurry_image):
        """Test assessment of blurry image from local file."""
        from tempfile import NamedTemporaryFile
        import os

        with NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(blurry_image)
            temp_path = Path(f.name)

        try:
            assessment = assessor.assess(image_path=temp_path)
            assert isinstance(assessment, QualityAssessment)
            assert assessment.sharpness_score < 50
            assert assessment.overall_score < 70
        finally:
            os.unlink(temp_path)

    def test_assess_nonexistent_file(self, assessor):
        """Test assessment of non-existent file."""
        fake_path = Path("/nonexistent/image.jpg")
        assessment = assessor.assess(image_path=fake_path)

        # Should return minimum scores on error
        assert assessment.sharpness_score == 0.0
        assert assessment.contrast_score == 0.0
        assert assessment.resolution_score == 0.0
        assert assessment.noise_score == 0.0
        assert assessment.overall_score == 0.0

    def test_assess_invalid_file_format(self, assessor):
        """Test assessment of invalid file format."""
        from tempfile import NamedTemporaryFile
        import os

        with NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"Not an image")
            temp_path = Path(f.name)

        try:
            assessment = assessor.assess(image_path=temp_path)

            # Should return minimum scores for invalid image
            assert assessment.sharpness_score == 0.0
            assert assessment.contrast_score == 0.0
            assert assessment.overall_score == 0.0
        finally:
            os.unlink(temp_path)

    def test_assess_with_dpi_metadata(self, assessor, high_dpi_image, low_dpi_image):
        """Test assessment correctly reads DPI metadata."""
        from tempfile import NamedTemporaryFile
        import os

        # Test high DPI image
        with NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(high_dpi_image)
            high_dpi_path = Path(f.name)

        try:
            assessment = assessor.assess(image_path=high_dpi_path)
            assert assessment.resolution_score >= 99  # 300 DPI should give near-max score
        finally:
            os.unlink(high_dpi_path)

        # Test low DPI image
        with NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(low_dpi_image)
            low_dpi_path = Path(f.name)

        try:
            assessment = assessor.assess(image_path=low_dpi_path)
            assert assessment.resolution_score < 30  # 72 DPI is low
        finally:
            os.unlink(low_dpi_path)