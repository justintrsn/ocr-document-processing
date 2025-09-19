"""
Contract tests for OCR API endpoint
Tests all endpoint contracts, error responses, and parameter validation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import base64
from typing import Dict, Any

try:
    from src.api.main import app
    from src.models.ocr_api import OCRRequest, OCRResponseFull, ProcessingOptions, ThresholdSettings
except ImportError:
    # For testing without full installation
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.api.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_image_base64():
    """Create a sample base64 encoded image"""
    # Create a minimal valid PNG image (1x1 pixel)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
    return base64.b64encode(png_data).decode('utf-8')


class TestOCREndpointContract:
    """Test OCR endpoint contract compliance"""

    def test_endpoint_exists(self, client):
        """Test that OCR endpoint exists"""
        response = client.post("/api/v1/ocr", json={})
        assert response.status_code in [422, 400]  # Should fail with validation error, not 404

    def test_minimal_valid_request(self, client, sample_image_base64):
        """Test minimal valid request structure"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {},
                "thresholds": {},
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200
            assert "status" in response.json()

    def test_full_request_structure(self, client, sample_image_base64):
        """Test complete request with all options"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {
                    "enable_quality_check": True,
                    "enable_ocr": True,
                    "enable_enhancement": True,
                    "enhancement_types": ["context"],
                    "return_format": "full"
                },
                "thresholds": {
                    "image_quality_threshold": 30,
                    "confidence_threshold": 80
                },
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "confidence_report" in data
            assert "metadata" in data

    def test_obs_url_source(self, client):
        """Test OBS URL source type"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            request_data = {
                "source": {
                    "type": "obs_url",
                    "obs_url": "obs://bucket/document.jpg"
                },
                "processing_options": {},
                "thresholds": {},
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200

    def test_async_processing(self, client, sample_image_base64):
        """Test async processing returns job_id"""
        with patch('src.api.endpoints.ocr.BackgroundTasks.add_task') as mock_task:
            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {},
                "thresholds": {},
                "async_processing": True
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert "status" in data
            assert data["status"] == "processing"

    def test_return_format_minimal(self, client, sample_image_base64):
        """Test minimal return format"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {
                    "return_format": "minimal"
                },
                "thresholds": {},
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "extracted_text" in data
            assert "routing_decision" in data
            assert "confidence_score" in data
            assert "document_id" in data

    def test_return_format_ocr_only(self, client, sample_image_base64):
        """Test OCR-only return format"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {
                    "return_format": "ocr_only"
                },
                "thresholds": {},
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "raw_text" in data
            assert "word_count" in data
            assert "ocr_confidence" in data
            assert "processing_time_ms" in data

    def test_invalid_source_type(self, client):
        """Test invalid source type validation"""
        request_data = {
            "source": {
                "type": "invalid_type",
                "file": "data"
            },
            "processing_options": {},
            "thresholds": {},
            "async_processing": False
        }

        response = client.post("/api/v1/ocr", json=request_data)
        assert response.status_code == 422
        assert "validation" in response.text.lower() or "error" in response.text.lower()

    def test_missing_file_for_file_type(self, client):
        """Test missing file when source type is file"""
        request_data = {
            "source": {
                "type": "file"
            },
            "processing_options": {},
            "thresholds": {},
            "async_processing": False
        }

        response = client.post("/api/v1/ocr", json=request_data)
        assert response.status_code == 422

    def test_missing_obs_url_for_obs_type(self, client):
        """Test missing OBS URL when source type is obs_url"""
        request_data = {
            "source": {
                "type": "obs_url"
            },
            "processing_options": {},
            "thresholds": {},
            "async_processing": False
        }

        response = client.post("/api/v1/ocr", json=request_data)
        assert response.status_code == 422

    def test_threshold_validation(self, client, sample_image_base64):
        """Test threshold value validation"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response()

            # Test valid thresholds (0-100)
            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "thresholds": {
                    "image_quality_threshold": 0,
                    "confidence_threshold": 100
                },
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 200

            # Test invalid thresholds (should fail)
            request_data["thresholds"]["image_quality_threshold"] = -1
            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 422

            request_data["thresholds"]["image_quality_threshold"] = 50
            request_data["thresholds"]["confidence_threshold"] = 101
            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 422

    def test_job_status_endpoint(self, client):
        """Test job status endpoint exists and returns proper format"""
        job_id = "test-job-123"

        # Mock the jobs storage
        with patch('src.api.endpoints.ocr.jobs') as mock_jobs:
            mock_jobs.get.return_value = {
                "status": "completed",
                "result": self._create_mock_response(),
                "created_at": "2025-01-19T10:00:00Z",
                "completed_at": "2025-01-19T10:00:30Z"
            }

            response = client.get(f"/api/v1/ocr/job/{job_id}")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "result" in data

    def test_job_not_found(self, client):
        """Test job status for non-existent job"""
        with patch('src.api.endpoints.ocr.jobs') as mock_jobs:
            mock_jobs.get.return_value = None

            response = client.get("/api/v1/ocr/job/non-existent-job")
            assert response.status_code == 404

    def test_error_handling(self, client, sample_image_base64):
        """Test error handling and response format"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.side_effect = Exception("Processing failed")

            request_data = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "async_processing": False
            }

            response = client.post("/api/v1/ocr", json=request_data)
            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data

    def _create_mock_response(self) -> Dict[str, Any]:
        """Create a mock processing response"""
        return {
            "status": "success",
            "quality_check": {
                "performed": True,
                "passed": True,
                "score": 85.0,
                "metrics": {
                    "sharpness": 85.0,
                    "contrast": 80.0,
                    "resolution": 90.0
                },
                "issues": []
            },
            "ocr_result": {
                "raw_text": "Sample OCR text",
                "word_count": 3,
                "confidence_score": 95.0,
                "confidence_distribution": {
                    "high": 3,
                    "medium": 0,
                    "low": 0
                }
            },
            "confidence_report": {
                "image_quality_score": 85.0,
                "ocr_confidence_score": 95.0,
                "final_confidence": 90.0,
                "routing_decision": "pass",
                "routing_reason": "All thresholds met",
                "quality_check_passed": True,
                "confidence_check_passed": True
            },
            "metadata": {
                "document_id": "doc-123",
                "timestamp": "2025-01-19T10:00:00Z",
                "processing_time_ms": 2500
            }
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])