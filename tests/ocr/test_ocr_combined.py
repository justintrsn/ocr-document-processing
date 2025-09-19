"""
Combined tests for OCR Service - Both Base64 and URL modes

This test suite demonstrates that the OCR service supports both:
1. Base64 mode - for local files (using 'data' field)
2. URL mode - for OBS files (using 'url' field)

Both methods are valid and work with the Huawei OCR API.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.ocr_service import HuaweiOCRService
from src.services.obs_service import OBSService


class TestOCRModes:
    """Test both OCR processing modes"""

    @pytest.fixture
    def ocr_service(self):
        """Create OCR service instance"""
        with patch('src.services.ocr_service.settings') as mock_settings:
            mock_settings.huawei_ocr_endpoint = "https://ocr.ap-southeast-3.myhuaweicloud.com"
            mock_settings.huawei_access_key = "test_access_key"
            mock_settings.huawei_secret_key = "test_secret_key"
            mock_settings.huawei_project_id = "test_project_id"
            mock_settings.huawei_region = "ap-southeast-3"
            mock_settings.api_timeout = 180
            mock_settings.ocr_url = "https://ocr.ap-southeast-3.myhuaweicloud.com/v2/test_project_id/ocr/smart-document-recognizer"
            mock_settings.image_optimal_size_mb = 7
            return HuaweiOCRService()

    @patch('src.services.ocr_service.requests.post')
    @patch('src.services.ocr_service.Image.open')
    def test_base64_mode(self, mock_image_open, mock_post, ocr_service):
        """Test OCR using base64 encoding (local file)"""
        # Mock image
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.save = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image

        # Mock responses
        mock_token_response = Mock()
        mock_token_response.status_code = 201
        mock_token_response.headers = {'X-Subject-Token': 'test_token'}

        mock_ocr_response = Mock()
        mock_ocr_response.status_code = 200
        mock_ocr_response.json.return_value = {
            "result": [{
                "ocr_result": {
                    "words_block_list": [
                        {"words": "Test Document", "confidence": 0.98}
                    ]
                }
            }]
        }

        mock_post.side_effect = [mock_token_response, mock_ocr_response]

        # Test with local file path
        test_path = Path("test_document.jpg")
        result = ocr_service.process_document(test_path)

        # Verify the request used 'data' field with base64
        ocr_call = mock_post.call_args_list[1]
        request_json = ocr_call[1]['json']
        assert 'data' in request_json  # Using 'data' field for base64
        assert 'url' not in request_json

    @patch('src.services.ocr_service.requests.post')
    def test_url_mode(self, mock_post, ocr_service):
        """Test OCR using URL (OBS file)"""
        # Mock responses
        mock_token_response = Mock()
        mock_token_response.status_code = 201
        mock_token_response.headers = {'X-Subject-Token': 'test_token'}

        mock_ocr_response = Mock()
        mock_ocr_response.status_code = 200
        mock_ocr_response.json.return_value = {
            "result": [{
                "ocr_result": {
                    "words_block_list": [
                        {"words": "Test Document", "confidence": 0.98}
                    ]
                }
            }]
        }

        mock_post.side_effect = [mock_token_response, mock_ocr_response]

        # Test with URL
        test_url = "https://bucket.obs.region.com/OCR/document.jpg?signature=xyz"
        result = ocr_service.process_document(image_url=test_url)

        # Verify the request used 'url' field
        ocr_call = mock_post.call_args_list[1]
        request_json = ocr_call[1]['json']
        assert 'url' in request_json  # Using 'url' field for URL
        assert request_json['url'] == test_url
        assert 'data' not in request_json

    @patch('src.services.ocr_service.requests.post')
    @patch('src.services.ocr_service.Image.open')
    def test_both_modes_produce_same_result(self, mock_image_open, mock_post, ocr_service):
        """Test that both modes produce similar results"""
        # Mock image for base64 mode
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.save = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image

        # Same OCR response for both modes
        ocr_response_data = {
            "result": [{
                "ocr_result": {
                    "words_block_list": [
                        {
                            "words": "Medical Certificate",
                            "confidence": 0.98,
                            "location": [[10, 10], [200, 10], [200, 30], [10, 30]]
                        },
                        {
                            "words": "Patient Name: John Doe",
                            "confidence": 0.95,
                            "location": [[10, 40], [250, 40], [250, 60], [10, 60]]
                        }
                    ],
                    "direction": 0.0,
                    "words_block_count": 2
                }
            }]
        }

        # Mock responses for base64 mode
        mock_token_response = Mock()
        mock_token_response.status_code = 201
        mock_token_response.headers = {'X-Subject-Token': 'test_token'}

        mock_ocr_response = Mock()
        mock_ocr_response.status_code = 200
        mock_ocr_response.json.return_value = ocr_response_data

        mock_post.side_effect = [
            mock_token_response, mock_ocr_response,  # For base64 mode
            mock_token_response, mock_ocr_response   # For URL mode
        ]

        # Test base64 mode
        test_path = Path("test_document.jpg")
        result_base64 = ocr_service.process_document(test_path)
        text_base64 = ocr_service.extract_text_from_response(result_base64)
        confidence_base64 = ocr_service.get_average_confidence(result_base64)

        # Test URL mode
        test_url = "https://bucket.obs.region.com/OCR/document.jpg"
        result_url = ocr_service.process_document(image_url=test_url)
        text_url = ocr_service.extract_text_from_response(result_url)
        confidence_url = ocr_service.get_average_confidence(result_url)

        # Both modes should produce the same results
        assert text_base64 == text_url
        assert confidence_base64 == confidence_url
        assert "Medical Certificate" in text_base64
        assert "Patient Name: John Doe" in text_base64

    def test_service_validates_input(self, ocr_service):
        """Test that service requires either path or URL"""
        with pytest.raises(ValueError) as exc:
            ocr_service.process_document()  # Neither path nor URL provided

        assert "Either image_path or image_url must be provided" in str(exc.value)