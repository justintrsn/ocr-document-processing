"""
Test combined image quality assessment scenarios
"""

import pytest
from pathlib import Path

from src.models.quality import QualityAssessment, QualityIssue


class TestCombinedAssessment:
    """Test combined assessment scenarios"""

    def test_assess_with_multiple_inputs(self, assessor, sharp_image):
        """Test that image_data takes precedence over other inputs."""
        from tempfile import NamedTemporaryFile
        import os

        # Create a temp file with blurry image
        with NamedTemporaryFile(suffix='.png', delete=False) as f:
            from tests.image_quality.fixtures import create_blurry_image
            f.write(create_blurry_image())
            temp_path = Path(f.name)

        try:
            # Provide both image_data and image_path
            # image_data should take precedence
            assessment = assessor.assess(
                image_data=sharp_image,
                image_path=temp_path
            )

            assert isinstance(assessment, QualityAssessment)
            assert assessment.sharpness_score > 70  # Sharp (from image_data)
        finally:
            os.unlink(temp_path)

    def test_assess_raises_without_input(self, assessor):
        """Test that assess raises error without any input."""
        with pytest.raises(ValueError, match="Either image_path, image_url, or image_data must be provided"):
            assessor.assess()

    def test_assess_invalid_image(self, assessor):
        """Test assessment of invalid image data."""
        invalid_data = b"not an image"
        assessment = assessor.assess(image_data=invalid_data)

        # Should return minimum scores
        assert assessment.sharpness_score == 0.0
        assert assessment.contrast_score == 0.0
        assert assessment.resolution_score == 0.0
        assert assessment.noise_score == 0.0
        assert assessment.overall_score == 0.0

    def test_get_enhancement_recommendations_poor_quality(self, assessor):
        """Test enhancement recommendations for poor quality image."""
        poor_assessment = QualityAssessment(
            sharpness_score=50.0,
            contrast_score=40.0,
            resolution_score=60.0,
            noise_score=50.0
        )

        recommendations = assessor.get_enhancement_recommendations(poor_assessment)

        assert "Apply sharpening filter" in recommendations
        assert "Enhance contrast using histogram equalization" in recommendations
        assert "Use higher resolution scan (minimum 300 DPI)" in recommendations
        assert "Apply noise reduction filter" in recommendations

    def test_get_enhancement_recommendations_good_quality(self, assessor):
        """Test enhancement recommendations for good quality image."""
        good_assessment = QualityAssessment(
            sharpness_score=85.0,
            contrast_score=80.0,
            resolution_score=90.0,
            noise_score=85.0
        )

        recommendations = assessor.get_enhancement_recommendations(good_assessment)

        assert len(recommendations) == 1
        assert "Image quality is sufficient for OCR" in recommendations[0]

    def test_get_enhancement_recommendations_mixed_quality(self, assessor):
        """Test enhancement recommendations for mixed quality issues."""
        mixed_assessment = QualityAssessment(
            sharpness_score=85.0,  # Good
            contrast_score=45.0,   # Poor
            resolution_score=90.0,  # Good
            noise_score=50.0       # Fair
        )

        recommendations = assessor.get_enhancement_recommendations(mixed_assessment)

        assert "Enhance contrast using histogram equalization" in recommendations
        assert "Apply noise reduction filter" in recommendations
        assert "Apply sharpening filter" not in recommendations
        assert "Use higher resolution scan" not in recommendations

    def test_quality_issue_detection(self, poor_quality_assessment):
        """Test quality issue detection."""
        poor_quality_assessment.detect_issues()

        assert len(poor_quality_assessment.issues) > 0

        # Check that issues are properly categorized
        issue_types = [issue.type for issue in poor_quality_assessment.issues]
        assert "blur" in issue_types or "contrast" in issue_types

        # Check severity levels
        severities = [issue.severity for issue in poor_quality_assessment.issues]
        assert "high" in severities or "medium" in severities

    def test_acceptability_check(self):
        """Test image acceptability determination."""
        from src.models.quality import QualityAssessment

        # Acceptable quality
        acceptable = QualityAssessment(
            sharpness_score=60.0,
            contrast_score=55.0,
            resolution_score=65.0,
            noise_score=60.0
        )
        assert acceptable.is_acceptable is True

        # Unacceptable due to low overall score
        unacceptable_low = QualityAssessment(
            sharpness_score=30.0,
            contrast_score=25.0,
            resolution_score=35.0,
            noise_score=30.0
        )
        assert unacceptable_low.is_acceptable is False

        # Unacceptable due to critical issue
        unacceptable_critical = QualityAssessment(
            sharpness_score=60.0,
            contrast_score=55.0,
            resolution_score=65.0,
            noise_score=60.0,
            issues=[QualityIssue(
                type="blur",
                severity="high",
                description="Severe blur",
                impact_on_ocr="Critical"
            )]
        )
        assert unacceptable_critical.is_acceptable is False

    def test_quality_assessment_to_dict(self, good_quality_assessment):
        """Test conversion to dictionary for API response."""
        good_quality_assessment.detect_issues()
        result = good_quality_assessment.to_dict()

        assert "overall_score" in result
        assert "quality_level" in result
        assert "is_acceptable" in result
        assert "scores" in result
        assert "issues" in result
        assert "recommendations" in result
        assert "image_properties" in result

        # Check structure
        assert isinstance(result["scores"], dict)
        assert "sharpness" in result["scores"]
        assert "contrast" in result["scores"]
        assert "resolution" in result["scores"]
        assert "noise" in result["scores"]

    def test_assessment_with_real_document(self, assessor, test_image_path):
        """Test assessment with real scanned document."""
        from tests.config import test_config

        if test_image_path.exists():
            assessment = assessor.assess(image_path=test_image_path)

            assert isinstance(assessment, QualityAssessment)
            assert assessment.overall_score > 0

            # Get recommendations
            recommendations = assessor.get_enhancement_recommendations(assessment)
            assert isinstance(recommendations, list)
            assert len(recommendations) > 0

            # Check if it meets OCR threshold from config
            ocr_threshold = test_config.get_ocr_threshold()
            if assessment.overall_score >= ocr_threshold:
                assert assessment.quality_level in ["excellent", "good"]
                print(f"✅ Document passes OCR threshold ({assessment.overall_score:.1f} >= {ocr_threshold})")
            else:
                assert assessment.quality_level in ["fair", "poor"]
                print(f"❌ Document fails OCR threshold ({assessment.overall_score:.1f} < {ocr_threshold})")

    def test_batch_assessment(self, assessor, sharp_image, blurry_image, noisy_image):
        """Test assessing multiple images in sequence."""
        images = [
            ("sharp", sharp_image),
            ("blurry", blurry_image),
            ("noisy", noisy_image)
        ]

        results = {}
        for name, image_data in images:
            assessment = assessor.assess(image_data=image_data)
            results[name] = assessment

        # Verify relative quality
        assert results["sharp"].overall_score > results["blurry"].overall_score
        assert results["sharp"].sharpness_score > results["blurry"].sharpness_score
        assert results["sharp"].noise_score > results["noisy"].noise_score