"""
Global pytest fixtures and test utilities
Provides sample documents, mock responses, and test configuration
"""

import pytest
import base64
import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock
from datetime import datetime
import os

# Use mock objects for models if imports fail
try:
    from src.models.ocr_models import OCRResponse, OCRResult, WordBlock
    from src.models.quality import QualityAssessment
    from src.models.api_models import ConfidenceReport, ProcessingResult
    from src.services.llm_enhancement_service import EnhancementResult, GrammarCorrection
except ImportError:
    # Create mock classes for testing
    from types import SimpleNamespace
    OCRResponse = SimpleNamespace
    OCRResult = SimpleNamespace
    WordBlock = SimpleNamespace
    QualityAssessment = SimpleNamespace
    ConfidenceReport = SimpleNamespace
    ProcessingResult = SimpleNamespace
    EnhancementResult = SimpleNamespace
    GrammarCorrection = SimpleNamespace


# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data"
DOCUMENTS_DIR = Path(__file__).parent / "documents"


@pytest.fixture
def sample_png_image():
    """Create a minimal valid PNG image"""
    # 1x1 pixel transparent PNG
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    return png_data


@pytest.fixture
def sample_image_base64():
    """Create base64 encoded sample image"""
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    return base64.b64encode(png_data).decode('utf-8')


@pytest.fixture
def sample_document_path():
    """Path to a sample document if it exists"""
    sample_path = DOCUMENTS_DIR / "scanned_document.jpg"
    if sample_path.exists():
        return str(sample_path)
    return None


@pytest.fixture
def mock_ocr_response():
    """Create a mock OCR response with typical structure"""
    return OCRResponse(
        result=[
            OCRResult(
                ocr_result={
                    "words_block_list": [
                        WordBlock(
                            words="Sample",
                            confidence=0.98,
                            location=[[0, 0], [100, 0], [100, 20], [0, 20]]
                        ),
                        WordBlock(
                            words="document",
                            confidence=0.95,
                            location=[[110, 0], [200, 0], [200, 20], [110, 20]]
                        ),
                        WordBlock(
                            words="text",
                            confidence=0.92,
                            location=[[210, 0], [250, 0], [250, 20], [210, 20]]
                        )
                    ],
                    "direction": 0.0
                }
            )
        ]
    )


@pytest.fixture
def mock_ocr_response_low_confidence():
    """Create a mock OCR response with low confidence scores"""
    return OCRResponse(
        result=[
            OCRResult(
                ocr_result={
                    "words_block_list": [
                        WordBlock(
                            words="Unclear",
                            confidence=0.65,
                            location=[[0, 0], [100, 0], [100, 20], [0, 20]]
                        ),
                        WordBlock(
                            words="text",
                            confidence=0.58,
                            location=[[110, 0], [200, 0], [200, 20], [110, 20]]
                        ),
                        WordBlock(
                            words="here",
                            confidence=0.72,
                            location=[[210, 0], [250, 0], [250, 20], [210, 20]]
                        )
                    ],
                    "direction": 0.0
                }
            )
        ]
    )


@pytest.fixture
def mock_quality_assessment_high():
    """Mock high quality assessment"""
    return QualityAssessment(
        sharpness_score=92.0,
        contrast_score=88.0,
        resolution_score=95.0,
        noise_level=3.0,
        overall_score=91.0,
        issues_detected=[],
        recommendations=[]
    )


@pytest.fixture
def mock_quality_assessment_low():
    """Mock low quality assessment"""
    return QualityAssessment(
        sharpness_score=45.0,
        contrast_score=38.0,
        resolution_score=50.0,
        noise_level=25.0,
        overall_score=25.0,
        issues_detected=["Low sharpness", "Poor contrast", "High noise"],
        recommendations=["Rescan at higher resolution", "Improve lighting"]
    )


@pytest.fixture
def mock_enhancement_result():
    """Mock LLM enhancement result"""
    return EnhancementResult(
        enhanced_text="Sample document text with corrections",
        corrections=[
            GrammarCorrection(
                original="documant",
                corrected="document",
                confidence=0.95,
                issue_type="spelling"
            )
        ],
        overall_confidence=0.92,
        summary="Fixed 1 spelling error"
    )


@pytest.fixture
def mock_confidence_report_pass():
    """Mock confidence report that passes thresholds"""
    return ConfidenceReport(
        image_quality_score=85.0,
        ocr_confidence_score=92.0,
        grammar_score=0.0,  # Disabled
        context_score=0.0,  # Disabled
        structure_score=0.0,  # Disabled
        final_confidence=88.5,  # (85 + 92) / 2
        weights={
            "image_quality": 0.5,
            "ocr": 0.5,
            "grammar": 0.0,
            "context": 0.0,
            "structure": 0.0
        },
        routing_decision="automatic",
        priority_level="low",
        issues_detected=[]
    )


@pytest.fixture
def mock_confidence_report_fail():
    """Mock confidence report that fails thresholds"""
    return ConfidenceReport(
        image_quality_score=25.0,
        ocr_confidence_score=65.0,
        grammar_score=0.0,  # Disabled
        context_score=0.0,  # Disabled
        structure_score=0.0,  # Disabled
        final_confidence=45.0,  # (25 + 65) / 2
        weights={
            "image_quality": 0.5,
            "ocr": 0.5,
            "grammar": 0.0,
            "context": 0.0,
            "structure": 0.0
        },
        routing_decision="manual_review",
        priority_level="high",
        issues_detected=["Low image quality", "Low OCR confidence"]
    )


@pytest.fixture
def mock_processing_result_success():
    """Mock successful processing result"""
    return ProcessingResult(
        document_id="test-doc-123",
        status="completed",
        extracted_text="Sample document text",
        enhanced_text="Sample document text with corrections",
        confidence_report=mock_confidence_report_pass(),
        quality_assessment=mock_quality_assessment_high(),
        processing_metrics={
            "total_processing_time": 3.5,
            "quality_check_time": 0.8,
            "ocr_processing_time": 2.2,
            "llm_enhancement_time": 0.5
        },
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        corrections_made=[
            {
                "original": "documant",
                "corrected": "document",
                "confidence": 0.95,
                "type": "spelling"
            }
        ]
    )


@pytest.fixture
def ocr_request_minimal():
    """Minimal OCR request"""
    return {
        "source": {
            "type": "file",
            "file": "<base64_encoded_file>"
        },
        "processing_options": {},
        "thresholds": {},
        "async_processing": False
    }


@pytest.fixture
def ocr_request_full():
    """Full OCR request with all options"""
    return {
        "source": {
            "type": "obs_url",
            "obs_url": "obs://bucket/document.jpg"
        },
        "processing_options": {
            "enable_quality_check": True,
            "enable_ocr": True,
            "enable_enhancement": True,
            "enhancement_types": ["complete"],
            "return_format": "full"
        },
        "thresholds": {
            "image_quality_threshold": 30,
            "confidence_threshold": 80
        },
        "async_processing": False
    }


@pytest.fixture
def ocr_request_quick():
    """Quick OCR request (no quality check, no enhancement)"""
    return {
        "source": {
            "type": "file",
            "file": "<base64_encoded_file>"
        },
        "processing_options": {
            "enable_quality_check": False,
            "enable_ocr": True,
            "enable_enhancement": False,
            "return_format": "ocr_only"
        },
        "thresholds": {
            "image_quality_threshold": 0,
            "confidence_threshold": 0
        },
        "async_processing": False
    }


# Test environment configuration
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables"""
    test_env = {
        "HUAWEI_OCR_ENDPOINT": "https://test-ocr.example.com",
        "HUAWEI_ACCESS_KEY": "test-access-key",
        "HUAWEI_SECRET_KEY": "test-secret-key",
        "HUAWEI_PROJECT_ID": "test-project-id",
        "MAAS_API_KEY": "test-maas-key",
        "MAAS_BASE_URL": "https://test-maas.example.com",
        "MAAS_MODEL_NAME": "test-model",
        "APP_ENV": "testing",
        "APP_DEBUG": "false",
        "LOG_LEVEL": "ERROR"  # Reduce log noise in tests
    }

    for key, value in test_env.items():
        if key not in os.environ:
            monkeypatch.setenv(key, value)


# Async test helpers
@pytest.fixture
def async_mock():
    """Create an async mock helper"""
    from unittest.mock import AsyncMock
    return AsyncMock


# Custom markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "contract: mark test as contract test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )