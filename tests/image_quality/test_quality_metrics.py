"""
Test individual quality metrics calculations
"""

import pytest
import numpy as np
import cv2

from src.models.quality import QualityAssessment


class TestQualityMetrics:
    """Test individual quality metric calculations"""

    def test_calculate_sharpness(self, assessor):
        """Test sharpness calculation."""
        # Create sharp edges
        sharp = np.zeros((100, 100), dtype=np.uint8)
        sharp[45:55, :] = 255
        sharp[:, 45:55] = 255

        # Create blurry image
        blurry = cv2.GaussianBlur(sharp, (15, 15), 5)

        sharp_score = assessor._calculate_sharpness(sharp)
        blurry_score = assessor._calculate_sharpness(blurry)

        assert sharp_score > blurry_score
        assert sharp_score > 0
        assert blurry_score >= 0

    def test_calculate_contrast(self, assessor):
        """Test contrast calculation."""
        # High contrast image
        high_contrast = np.zeros((100, 100), dtype=np.uint8)
        high_contrast[::2, ::2] = 255

        # Low contrast image
        low_contrast = np.ones((100, 100), dtype=np.uint8) * 128
        low_contrast[40:60, 40:60] = 136

        high_score = assessor._calculate_contrast(high_contrast)
        low_score = assessor._calculate_contrast(low_contrast)

        assert high_score > low_score
        assert high_score > 0
        assert low_score >= 0

    def test_calculate_noise_level(self, assessor):
        """Test noise level calculation."""
        # Clean image
        clean = np.ones((100, 100), dtype=np.uint8) * 128

        # Noisy image
        noisy = clean.copy()
        noise = np.random.randint(0, 50, (100, 100), dtype=np.uint8)
        noisy = np.clip(noisy.astype(int) + noise - 25, 0, 255).astype(np.uint8)

        clean_noise = assessor._calculate_noise_level(clean)
        high_noise = assessor._calculate_noise_level(noisy)

        assert high_noise > clean_noise
        assert 0 <= clean_noise <= 1
        assert 0 <= high_noise <= 1

    def test_calculate_resolution_from_dpi(self, assessor, high_dpi_image, low_dpi_image):
        """Test resolution calculation from DPI metadata."""
        high_resolution = assessor._calculate_resolution(high_dpi_image)
        low_resolution = assessor._calculate_resolution(low_dpi_image)

        # Test relative comparison instead of absolute values
        # High DPI should be significantly higher than low DPI
        assert high_resolution > low_resolution * 3  # 300 DPI vs 72 DPI
        assert low_resolution < 75    # Low DPI image (with tolerance for rounding)

    def test_calculate_resolution_no_dpi(self, assessor):
        """Test resolution calculation when no DPI info available."""
        # Create image without DPI metadata
        from PIL import Image
        from io import BytesIO

        img = Image.new('RGB', (100, 100), color='white')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')  # JPEG without explicit DPI

        resolution = assessor._calculate_resolution(buffer.getvalue())
        assert resolution == 72.0  # Default DPI

    def test_sharpness_scoring(self, assessor, sharp_image, blurry_image):
        """Test sharpness scoring normalization."""
        sharp_assessment = assessor.assess(image_data=sharp_image)
        blurry_assessment = assessor.assess(image_data=blurry_image)

        assert 0 <= sharp_assessment.sharpness_score <= 100
        assert 0 <= blurry_assessment.sharpness_score <= 100
        assert sharp_assessment.sharpness_score > blurry_assessment.sharpness_score

    def test_contrast_scoring(self, assessor, sharp_image, low_contrast_image):
        """Test contrast scoring normalization."""
        normal_assessment = assessor.assess(image_data=sharp_image)
        low_assessment = assessor.assess(image_data=low_contrast_image)

        assert 0 <= normal_assessment.contrast_score <= 100
        assert 0 <= low_assessment.contrast_score <= 100
        assert normal_assessment.contrast_score > low_assessment.contrast_score

    def test_noise_scoring(self, assessor, sharp_image, noisy_image):
        """Test noise scoring (inverse - higher score means less noise)."""
        clean_assessment = assessor.assess(image_data=sharp_image)
        noisy_assessment = assessor.assess(image_data=noisy_image)

        assert 0 <= clean_assessment.noise_score <= 100
        assert 0 <= noisy_assessment.noise_score <= 100
        assert clean_assessment.noise_score > noisy_assessment.noise_score

    def test_overall_score_calculation(self, assessor):
        """Test overall score weighted calculation."""
        from src.models.quality import QualityAssessment

        assessment = QualityAssessment(
            sharpness_score=80.0,
            contrast_score=70.0,
            resolution_score=90.0,
            noise_score=85.0,
            brightness_score=75.0,
            text_orientation_score=95.0
        )

        # Weights: sharpness(0.3), contrast(0.25), resolution(0.2),
        #          noise(0.15), brightness(0.05), orientation(0.05)
        expected = (
            80.0 * 0.3 +
            70.0 * 0.25 +
            90.0 * 0.2 +
            85.0 * 0.15 +
            75.0 * 0.05 +
            95.0 * 0.05
        )

        assert abs(assessment.overall_score - expected) < 0.01

    def test_quality_level_classification(self, assessor):
        """Test quality level classification based on overall score."""
        from src.models.quality import QualityAssessment

        # Excellent (>=80)
        excellent = QualityAssessment(
            sharpness_score=90.0,
            contrast_score=85.0,
            resolution_score=90.0,
            noise_score=85.0
        )
        assert excellent.quality_level == "excellent"

        # Good (60-79)
        good = QualityAssessment(
            sharpness_score=70.0,
            contrast_score=65.0,
            resolution_score=70.0,
            noise_score=65.0
        )
        assert good.quality_level == "good"

        # Fair (40-59)
        fair = QualityAssessment(
            sharpness_score=50.0,
            contrast_score=45.0,
            resolution_score=50.0,
            noise_score=45.0
        )
        assert fair.quality_level == "fair"

        # Poor (<40)
        poor = QualityAssessment(
            sharpness_score=30.0,
            contrast_score=25.0,
            resolution_score=30.0,
            noise_score=25.0
        )
        assert poor.quality_level == "poor"