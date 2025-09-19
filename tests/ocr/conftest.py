"""
Pytest configuration and fixtures for OCR tests
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import base64

from tests.ocr.fixtures import (
    TEST_IMAGE_PATH,
    SAMPLE_OCR_RESPONSE,
    OBS_TEST_KEY,
    get_test_image_bytes
)


@pytest.fixture
def test_image_path():
    """Provide path to test image"""
    return TEST_IMAGE_PATH


@pytest.fixture
def test_image_bytes():
    """Provide test image as bytes"""
    return get_test_image_bytes()


@pytest.fixture
def test_image_base64():
    """Provide test image as base64 string"""
    return base64.b64encode(get_test_image_bytes()).decode('utf-8')


@pytest.fixture
def sample_ocr_response():
    """Provide sample OCR response for mocking"""
    return SAMPLE_OCR_RESPONSE


@pytest.fixture
def mock_ocr_service():
    """Create mocked OCR service"""
    with patch('src.services.ocr_service.settings') as mock_settings:
        mock_settings.huawei_ocr_endpoint = "https://ocr.ap-southeast-3.myhuaweicloud.com"
        mock_settings.huawei_access_key = "test_access_key"
        mock_settings.huawei_secret_key = "test_secret_key"
        mock_settings.huawei_project_id = "test_project_id"
        mock_settings.huawei_region = "ap-southeast-3"
        mock_settings.api_timeout = 180
        mock_settings.ocr_url = "https://ocr.ap-southeast-3.myhuaweicloud.com/v2/test_project_id/ocr/smart-document-recognizer"
        mock_settings.image_optimal_size_mb = 7

        from src.services.ocr_service import HuaweiOCRService
        return HuaweiOCRService()


@pytest.fixture
def mock_obs_service():
    """Create mocked OBS service"""
    with patch('src.services.obs_service.ObsClient') as mock_obs_client:
        with patch('src.services.obs_service.settings') as mock_settings:
            mock_settings.huawei_access_key = "test_access_key"
            mock_settings.huawei_secret_key = "test_secret_key"
            mock_settings.obs_endpoint = "https://obs.ap-southeast-3.myhuaweicloud.com"
            mock_settings.obs_bucket_name = "test-bucket"

            from src.services.obs_service import OBSService
            service = OBSService()
            service.obs_client = mock_obs_client
            return service


@pytest.fixture
def mock_token_response():
    """Mock IAM token response"""
    response = Mock()
    response.status_code = 201
    response.headers = {'X-Subject-Token': 'test_token_12345'}
    return response


@pytest.fixture
def mock_ocr_success_response(sample_ocr_response):
    """Mock successful OCR API response"""
    response = Mock()
    response.status_code = 200
    response.json.return_value = sample_ocr_response
    return response


@pytest.fixture
def mock_signed_url():
    """Mock signed URL for OBS"""
    return "https://test-bucket.obs.ap-southeast-3.myhuaweicloud.com/OCR/document.jpg?signature=xyz123"


@pytest.fixture
def mock_obs_list_response():
    """Mock OBS list objects response"""
    response = Mock()
    response.status = 200
    response.body = Mock()
    response.body.contents = [
        Mock(key='OCR/document1.jpg', size=1024, lastModified='2025-01-18T10:00:00', etag='abc123'),
        Mock(key='OCR/document2.pdf', size=2048, lastModified='2025-01-18T11:00:00', etag='def456'),
        Mock(key='OCR/medical/report.png', size=3072, lastModified='2025-01-18T12:00:00', etag='ghi789')
    ]
    return response