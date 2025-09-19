"""
Pytest configuration and fixtures for image quality tests
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from tests.image_quality.fixtures import (
    TEST_IMAGE_PATH,
    OBS_TEST_KEY,
    get_test_image_bytes,
    create_sharp_image,
    create_blurry_image,
    create_low_contrast_image,
    create_noisy_image,
    create_high_dpi_image,
    create_low_dpi_image,
    QUALITY_THRESHOLDS,
    get_all_test_documents,
    get_all_test_document_bytes,
    get_all_obs_test_keys
)
from tests.config import test_config


@pytest.fixture
def assessor():
    """Create image quality assessor instance."""
    from src.services.image_quality_service import ImageQualityAssessor
    return ImageQualityAssessor()


@pytest.fixture
def test_image_path():
    """Provide path to test image"""
    return TEST_IMAGE_PATH


@pytest.fixture
def test_image_bytes():
    """Provide test image as bytes"""
    return get_test_image_bytes()


@pytest.fixture
def sharp_image():
    """Create a sharp test image."""
    return create_sharp_image()


@pytest.fixture
def blurry_image():
    """Create a blurry test image."""
    return create_blurry_image()


@pytest.fixture
def low_contrast_image():
    """Create a low contrast test image."""
    return create_low_contrast_image()


@pytest.fixture
def noisy_image():
    """Create a noisy test image."""
    return create_noisy_image()


@pytest.fixture
def high_dpi_image():
    """Create image with high DPI metadata."""
    return create_high_dpi_image()


@pytest.fixture
def low_dpi_image():
    """Create image with low DPI metadata."""
    return create_low_dpi_image()


@pytest.fixture
def quality_thresholds():
    """Provide quality thresholds for testing"""
    return QUALITY_THRESHOLDS


@pytest.fixture
def mock_obs_service():
    """Create mocked OBS service for image quality tests"""
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
def mock_signed_url():
    """Mock signed URL for OBS"""
    return "https://test-bucket.obs.ap-southeast-3.myhuaweicloud.com/OCR/document.jpg?signature=xyz123"


@pytest.fixture
def temp_image_file(sharp_image):
    """Create a temporary image file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(sharp_image)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        os.unlink(temp_path)


@pytest.fixture
def poor_quality_assessment():
    """Create a poor quality assessment for testing"""
    from src.models.quality import QualityAssessment
    return QualityAssessment(
        sharpness_score=30.0,
        contrast_score=25.0,
        resolution_score=40.0,
        noise_score=35.0,
        brightness_score=50.0,
        text_orientation_score=60.0
    )


@pytest.fixture
def good_quality_assessment():
    """Create a good quality assessment for testing"""
    from src.models.quality import QualityAssessment
    return QualityAssessment(
        sharpness_score=85.0,
        contrast_score=80.0,
        resolution_score=90.0,
        noise_score=85.0,
        brightness_score=80.0,
        text_orientation_score=95.0
    )


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for URL testing"""
    with patch('src.services.image_quality_service.requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def all_test_documents():
    """Get all test documents based on configuration"""
    return get_all_test_documents()


@pytest.fixture
def all_test_document_bytes():
    """Get all test documents as bytes"""
    return get_all_test_document_bytes()


@pytest.fixture
def all_obs_test_keys():
    """Get all OBS test keys"""
    return get_all_obs_test_keys()


@pytest.fixture(params=get_all_test_documents())
def each_test_document(request):
    """Parametrized fixture that yields each test document"""
    return request.param


@pytest.fixture(params=get_all_test_document_bytes())
def each_test_document_bytes(request):
    """Parametrized fixture that yields each test document as bytes"""
    return request.param