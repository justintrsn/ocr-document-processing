"""
Tests for OCR Service using Base64 encoding (Local Files)

This test suite covers:
- Processing local image files by converting them to base64
- Direct API calls using the 'data' field
- Image compression and preparation
- Error handling for local file processing
- IAM token authentication

Use case: Testing OCR functionality with local files without OBS
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import base64

from src.services.ocr_service import HuaweiOCRService
from src.models.ocr_models import OCRResponse, ResultItem, OCRResult, WordBlock


@pytest.fixture
def ocr_service():
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


@pytest.fixture
def sample_ocr_response():
    return {
        "result": [{
            "ocr_result": {
                "words_block_list": [
                    {
                        "words": "Sample Document",
                        "confidence": 0.98,
                        "location": [[10, 10], [100, 10], [100, 30], [10, 30]]
                    },
                    {
                        "words": "This is a test document",
                        "confidence": 0.95,
                        "location": [[10, 40], [200, 40], [200, 60], [10, 60]]
                    }
                ],
                "direction": 0.0,
                "words_block_count": 2
            }
        }]
    }


class TestHuaweiOCRService:
    def test_ocr_service_initialization(self, ocr_service):
        assert ocr_service.endpoint == "https://ocr.ap-southeast-3.myhuaweicloud.com"
        assert ocr_service.access_key == "test_access_key"
        assert ocr_service.secret_key == "test_secret_key"
        assert ocr_service.project_id == "test_project_id"
        assert ocr_service.region == "ap-southeast-3"

    @patch('src.services.ocr_service.requests.post')
    @patch('src.services.ocr_service.Image.open')
    def test_process_document_success(self, mock_image_open, mock_post, ocr_service, sample_ocr_response):
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.save = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_ocr_response
        mock_post.return_value = mock_response

        test_image_path = Path("test_document.jpg")
        result = ocr_service.process_document(test_image_path)

        assert isinstance(result, OCRResponse)
        assert len(result.result) == 1
        assert len(result.result[0].ocr_result.words_block_list) == 2
        assert result.result[0].ocr_result.words_block_list[0].words == "Sample Document"
        assert result.result[0].ocr_result.words_block_list[0].confidence == 0.98

    @patch('src.services.ocr_service.requests.post')
    @patch('src.services.ocr_service.Image.open')
    def test_process_document_api_error(self, mock_image_open, mock_post, ocr_service):
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.save = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Invalid image format"
        mock_post.return_value = mock_response

        test_image_path = Path("test_document.jpg")

        with pytest.raises(Exception) as exc_info:
            ocr_service.process_document(test_image_path)

        assert "OCR API error: 400" in str(exc_info.value)

    def test_extract_text_from_response(self, ocr_service, sample_ocr_response):
        ocr_response = OCRResponse.model_validate(sample_ocr_response)
        extracted_text = ocr_service.extract_text_from_response(ocr_response)

        assert extracted_text == "Sample Document\nThis is a test document"

    def test_get_average_confidence(self, ocr_service, sample_ocr_response):
        ocr_response = OCRResponse.model_validate(sample_ocr_response)
        avg_confidence = ocr_service.get_average_confidence(ocr_response)

        expected_avg = (0.98 + 0.95) / 2
        assert avg_confidence == expected_avg

    def test_get_average_confidence_empty_response(self, ocr_service):
        empty_response = OCRResponse(result=[])
        avg_confidence = ocr_service.get_average_confidence(empty_response)

        assert avg_confidence == 0.0

    @patch('src.services.ocr_service.Image.open')
    def test_prepare_image_compression(self, mock_image_open, ocr_service):
        mock_image = MagicMock()
        mock_image.mode = 'RGB'

        saved_bytes = []

        def save_side_effect(byte_arr, **kwargs):
            quality = kwargs.get('quality', 95)
            if quality >= 90:
                byte_arr.write(b'x' * (8 * 1024 * 1024))
            else:
                byte_arr.write(b'x' * (5 * 1024 * 1024))

        mock_image.save = MagicMock(side_effect=save_side_effect)
        mock_image_open.return_value.__enter__.return_value = mock_image

        test_image_path = Path("large_image.jpg")
        base64_image = ocr_service._prepare_image(test_image_path)

        assert isinstance(base64_image, str)
        assert mock_image.save.call_count > 1

    def test_signature_creation(self, ocr_service):
        method = "POST"
        uri = f"/v2/{ocr_service.project_id}/ocr/smart-document-recognizer"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Sdk-Date": "20250118T120000Z",
            "X-Project-Id": ocr_service.project_id,
            "Host": "ocr.ap-southeast-3.myhuaweicloud.com"
        }

        signature = ocr_service._create_signature(method, uri, headers)

        assert signature.startswith("SDK-HMAC-SHA256")
        assert "Access=" in signature
        assert "SignedHeaders=" in signature
        assert "Signature=" in signature