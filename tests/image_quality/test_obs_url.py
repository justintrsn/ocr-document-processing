"""
Test image quality assessment for OBS URLs
"""

import pytest
from unittest.mock import MagicMock, patch

from src.models.quality import QualityAssessment


class TestOBSImageQuality:
    """Test image quality assessment for OBS URLs"""

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_from_public_url(self, mock_get, assessor, sharp_image):
        """Test assessment from public URL."""
        mock_response = MagicMock()
        mock_response.content = sharp_image
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url='https://example.com/image.png')

        assert isinstance(assessment, QualityAssessment)
        assert assessment.sharpness_score > 70
        mock_get.assert_called_once_with('https://example.com/image.png', timeout=30)

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_from_obs_key(self, mock_get, assessor, sharp_image):
        """Test assessment from OBS object key."""
        mock_response = MagicMock()
        mock_response.content = sharp_image
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with patch.object(assessor, '_get_obs_service') as mock_obs:
            mock_obs_service = MagicMock()
            mock_obs_service.get_signed_url.return_value = 'https://obs.example.com/signed-url'
            mock_obs.return_value = mock_obs_service

            assessment = assessor.assess(image_url='OCR/document.png')

            assert isinstance(assessment, QualityAssessment)
            assert assessment.sharpness_score > 70
            mock_obs_service.get_signed_url.assert_called_once_with('OCR/document.png')
            mock_get.assert_called_once_with('https://obs.example.com/signed-url', timeout=30)

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_from_signed_url(self, mock_get, assessor, test_image_bytes, mock_signed_url):
        """Test assessment from signed OBS URL."""
        mock_response = MagicMock()
        mock_response.content = test_image_bytes
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url=mock_signed_url)

        assert isinstance(assessment, QualityAssessment)
        assert assessment.overall_score > 0
        mock_get.assert_called_once_with(mock_signed_url, timeout=30)

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_blurry_from_url(self, mock_get, assessor, blurry_image):
        """Test assessment of blurry image from URL."""
        mock_response = MagicMock()
        mock_response.content = blurry_image
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url='https://example.com/blurry.png')

        assert isinstance(assessment, QualityAssessment)
        assert assessment.sharpness_score < 50
        assert assessment.overall_score < 70

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_low_contrast_from_url(self, mock_get, assessor, low_contrast_image):
        """Test assessment of low contrast image from URL."""
        mock_response = MagicMock()
        mock_response.content = low_contrast_image
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url='https://example.com/low_contrast.png')

        assert isinstance(assessment, QualityAssessment)
        assert assessment.contrast_score < 50
        assert assessment.overall_score < 70

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_noisy_from_url(self, mock_get, assessor, noisy_image):
        """Test assessment of noisy image from URL."""
        mock_response = MagicMock()
        mock_response.content = noisy_image
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url='https://example.com/noisy.png')

        assert isinstance(assessment, QualityAssessment)
        assert assessment.noise_score < 100  # Noisy images have lower noise scores

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_url_error(self, mock_get, assessor):
        """Test assessment handles URL fetch errors."""
        mock_get.side_effect = Exception("Network error")

        assessment = assessor.assess(image_url='https://example.com/error.png')

        # Should return minimum scores on error
        assert assessment.sharpness_score == 0.0
        assert assessment.contrast_score == 0.0
        assert assessment.resolution_score == 0.0
        assert assessment.noise_score == 0.0
        assert assessment.overall_score == 0.0

    @patch('src.services.image_quality_service.requests.get')
    def test_assess_url_404(self, mock_get, assessor):
        """Test assessment handles 404 errors."""
        from requests.exceptions import HTTPError
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        assessment = assessor.assess(image_url='https://example.com/notfound.png')

        # Should return minimum scores on error
        assert assessment.overall_score == 0.0

    def test_assess_with_obs_service_integration(self, assessor, sharp_image):
        """Test OBS service integration."""
        with patch('src.services.obs_service.ObsClient') as mock_obs_client:
            with patch('src.services.image_quality.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.content = sharp_image
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                # Mock OBS client response for signed URL
                mock_signed_response = MagicMock()
                mock_signed_response.signedUrl = 'https://obs.signed.url/image'
                mock_obs_client.return_value.createSignedUrl.return_value = mock_signed_response

                assessment = assessor.assess(image_url='OCR/test.jpg')

                assert isinstance(assessment, QualityAssessment)
                assert assessment.overall_score > 0