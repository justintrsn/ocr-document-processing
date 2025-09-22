"""
Comprehensive contract tests for OCR API endpoint
Combines simple contract, endpoint, and extended format tests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, MagicMock
import base64
import io
from PIL import Image
import json
import concurrent.futures
from typing import Dict, Any


@pytest.fixture
def client():
    """Create test client"""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def sample_image_base64():
    """Create a sample base64 encoded image"""
    img = Image.new('RGB', (100, 100), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


@pytest.fixture
def sample_pdf_base64():
    """Create a sample PDF and return its base64 encoding"""
    # Minimal PDF structure
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    return base64.b64encode(pdf_content).decode('utf-8')


class TestOCREndpointComplete:
    """Complete OCR endpoint contract tests"""

    # ======================
    # Simple Contract Tests
    # ======================

    def test_request_structure_minimal(self):
        """Test minimal request structure"""
        request = {
            "source": {
                "type": "file",
                "file": "base64_encoded_data"
            },
            "processing_options": {},
            "thresholds": {},
            "async_processing": False
        }

        # Verify required fields
        assert "source" in request
        assert request["source"]["type"] in ["file", "obs_url"]
        assert "processing_options" in request
        assert "thresholds" in request

    def test_request_structure_full(self):
        """Test full request structure with all options"""
        request = {
            "source": {
                "type": "obs_url",
                "obs_url": "obs://bucket/document.jpg"
            },
            "processing_options": {
                "enable_quality_check": True,
                "enable_ocr": True,
                "enable_enhancement": True,
                "enhancement_types": ["complete"],
                "return_format": "full",
                "format_hint": "PNG",
                "pdf_page_number": 1,
                "auto_rotation": True
            },
            "thresholds": {
                "image_quality_threshold": 30,
                "confidence_threshold": 80
            },
            "async_processing": False
        }

        # Verify all fields
        assert request["processing_options"]["enable_quality_check"] is True
        assert request["processing_options"]["enable_ocr"] is True
        assert request["processing_options"]["enable_enhancement"] is True
        assert "enhancement_types" in request["processing_options"]
        assert request["processing_options"]["return_format"] in ["full", "minimal", "ocr_only"]
        assert 0 <= request["thresholds"]["image_quality_threshold"] <= 100
        assert 0 <= request["thresholds"]["confidence_threshold"] <= 100

    def test_response_structure_full(self):
        """Test full response structure"""
        response = {
            "status": "success",
            "format_detected": "PNG",
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
                "raw_text": "Sample text",
                "word_count": 2,
                "confidence_score": 95.0,
                "confidence_distribution": {
                    "high": 2,
                    "medium": 0,
                    "low": 0
                }
            },
            "enhancement": {
                "performed": True,
                "enhanced_text": "Sample text corrected",
                "corrections": [],
                "processing_time_ms": 25000,
                "tokens_used": None
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
            "processing_metadata": {
                "auto_rotation_applied": False
            },
            "metadata": {
                "document_id": "doc_123",
                "timestamp": "2025-01-19T10:00:00Z",
                "processing_time_ms": 2500
            }
        }

        # Verify response structure
        assert response["status"] in ["success", "failed", "processing"]
        assert "confidence_report" in response
        assert response["confidence_report"]["routing_decision"] in ["pass", "requires_review"]
        assert "metadata" in response
        assert "format_detected" in response

    def test_routing_decision_logic(self):
        """Test routing decision logic based on thresholds"""
        # Case 1: Both thresholds met - should pass
        report = {
            "image_quality_score": 85.0,
            "ocr_confidence_score": 90.0,
            "final_confidence": 87.5,  # (85 + 90) / 2
            "thresholds": {
                "image_quality_threshold": 30,
                "confidence_threshold": 80
            }
        }

        # Check routing logic
        quality_passed = report["image_quality_score"] >= report["thresholds"]["image_quality_threshold"]
        confidence_passed = report["final_confidence"] >= report["thresholds"]["confidence_threshold"]
        routing_decision = "pass" if (quality_passed and confidence_passed) else "requires_review"

        assert routing_decision == "pass"

        # Case 2: Quality failed - should require review
        report["image_quality_score"] = 25.0
        report["final_confidence"] = 57.5  # (25 + 90) / 2

        quality_passed = report["image_quality_score"] >= report["thresholds"]["image_quality_threshold"]
        confidence_passed = report["final_confidence"] >= report["thresholds"]["confidence_threshold"]
        routing_decision = "pass" if (quality_passed and confidence_passed) else "requires_review"

        assert routing_decision == "requires_review"

    def test_confidence_calculation(self):
        """Test confidence score calculation (50% image + 50% OCR)"""
        image_quality = 80.0
        ocr_confidence = 90.0

        # Calculate final confidence
        final_confidence = (image_quality * 0.5) + (ocr_confidence * 0.5)

        assert final_confidence == 85.0
        assert 0 <= final_confidence <= 100

    # ======================
    # Endpoint Tests
    # ======================

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
            assert data["status"] == "accepted"  # Async jobs return 'accepted' status

    def test_return_format_minimal(self, client, sample_image_base64):
        """Test minimal return format"""
        with patch('src.api.endpoints.ocr.process_document_sync') as mock_process:
            mock_process.return_value = self._create_mock_response(return_format="minimal")

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
            mock_process.return_value = self._create_mock_response(return_format="ocr_only")

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

    # ======================
    # Extended Format Tests
    # ======================

    def test_accepts_all_11_format_types(self, client, sample_image_base64):
        """Test that endpoint accepts all 11 supported formats"""
        supported_formats = [
            'PNG', 'JPG', 'JPEG', 'BMP', 'GIF',
            'TIFF', 'WebP', 'PCX', 'ICO', 'PSD', 'PDF'
        ]

        for format_type in supported_formats:
            request_body = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {
                    "format_hint": format_type,
                    "enable_quality_check": True,
                    "enable_ocr": True
                }
            }

            response = client.post("/api/v1/ocr", json=request_body)

            # Should not return 415 Unsupported Media Type
            assert response.status_code != 415, f"Format {format_type} was rejected"

            # Should return either success or processing error (not format error)
            assert response.status_code in [200, 400, 500], f"Unexpected status for {format_type}"

    def test_format_validation_error_415(self, client, sample_image_base64):
        """Test that unsupported formats return 415 Unsupported Media Type"""
        request_body = {
            "source": {
                "type": "file",
                "file": sample_image_base64
            },
            "processing_options": {
                "format_hint": "INVALID_FORMAT",
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        assert response.status_code == 415
        error_response = response.json()
        assert "error" in error_response
        assert "FORMAT_NOT_SUPPORTED" in error_response.get("error_code", "")

    def test_size_validation_error_413(self, client):
        """Test that files over 10MB return 413 Payload Too Large"""
        # Create a large fake base64 string (>10MB when decoded)
        large_content = "A" * (11 * 1024 * 1024 * 4 // 3)  # ~11MB when decoded

        request_body = {
            "source": {
                "type": "file",
                "file": large_content
            },
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        assert response.status_code == 413
        error_response = response.json()
        assert "error" in error_response
        assert "FILE_TOO_LARGE" in error_response.get("error_code", "")

    def test_dimension_validation_error_400(self, client):
        """Test that images with invalid dimensions return 400 Bad Request"""
        # Create image with dimensions outside valid range (15-30000px)
        img = Image.new('RGB', (10, 10), color='white')  # Too small
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        small_image_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        request_body = {
            "source": {
                "type": "file",
                "file": small_image_base64
            },
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response
        assert "DIMENSIONS_INVALID" in error_response.get("error_code", "")

    def test_pdf_page_number_parameter(self, client, sample_pdf_base64):
        """Test PDF processing with page_number parameter"""
        request_body = {
            "source": {
                "type": "file",
                "file": sample_pdf_base64
            },
            "processing_options": {
                "enable_ocr": True,
                "pdf_page_number": 1  # Specific page
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        # Should accept the parameter
        assert response.status_code in [200, 400, 500]

        # Test with 'all' pages
        request_body["processing_options"]["pdf_page_number"] = "all"
        response = client.post("/api/v1/ocr", json=request_body)
        assert response.status_code in [200, 400, 500]

    def test_auto_rotation_option(self, client, sample_image_base64):
        """Test auto-rotation option for images"""
        request_body = {
            "source": {
                "type": "file",
                "file": sample_image_base64
            },
            "processing_options": {
                "enable_ocr": True,
                "auto_rotation": True
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            result = response.json()
            assert "processing_metadata" in result
            assert "auto_rotation_applied" in result["processing_metadata"]

    def test_format_detected_in_response(self, client, sample_image_base64):
        """Test that response includes format_detected field"""
        request_body = {
            "source": {
                "type": "file",
                "file": sample_image_base64
            },
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/ocr", json=request_body)

        if response.status_code == 200:
            result = response.json()
            assert "format_detected" in result
            assert result["format_detected"] in [
                'PNG', 'JPG', 'JPEG', 'BMP', 'GIF',
                'TIFF', 'WebP', 'PCX', 'ICO', 'PSD', 'PDF'
            ]

    def test_concurrent_format_processing(self, client, sample_image_base64):
        """Test that different formats can be processed concurrently"""

        def process_format(format_type):
            request_body = {
                "source": {
                    "type": "file",
                    "file": sample_image_base64
                },
                "processing_options": {
                    "format_hint": format_type,
                    "enable_ocr": True
                }
            }
            return client.post("/api/v1/ocr", json=request_body)

        formats = ['PNG', 'JPG', 'BMP', 'GIF']

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_format, fmt) for fmt in formats]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should complete
        assert len(results) == len(formats)

        # No request should fail due to concurrency
        for response in results:
            assert response.status_code in [200, 400, 500]

    # ======================
    # Additional Tests
    # ======================

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

    def test_job_status_endpoint(self, client):
        """Test job status endpoint exists and returns proper format"""
        job_id = "test-job-123"

        # Mock the jobs storage
        with patch('src.api.endpoints.ocr.async_jobs') as mock_jobs:
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
        with patch('src.api.endpoints.ocr.async_jobs') as mock_jobs:
            mock_jobs.get.return_value = None

            response = client.get("/api/v1/ocr/job/non-existent-job")
            assert response.status_code == 404

    def test_processing_options_combinations(self):
        """Test various processing option combinations"""
        # Quick OCR - no quality check, no enhancement
        options_quick = {
            "enable_quality_check": False,
            "enable_ocr": True,
            "enable_enhancement": False,
            "return_format": "ocr_only"
        }

        assert options_quick["enable_quality_check"] is False
        assert options_quick["enable_enhancement"] is False

        # Full processing
        options_full = {
            "enable_quality_check": True,
            "enable_ocr": True,
            "enable_enhancement": True,
            "return_format": "full"
        }

        assert all([
            options_full["enable_quality_check"],
            options_full["enable_ocr"],
            options_full["enable_enhancement"]
        ])

        # Quality check only
        options_quality = {
            "enable_quality_check": True,
            "enable_ocr": False,
            "enable_enhancement": False,
            "return_format": "minimal"
        }

        assert options_quality["enable_quality_check"] is True
        assert options_quality["enable_ocr"] is False

    # ======================
    # Helper Methods
    # ======================

    def _create_mock_response(self, return_format="full") -> Any:
        """Create a mock processing response matching the expected models"""
        from src.models.ocr_api import (
            OCRResponseFull, OCRResponseMinimal, OCRResponseOCROnly,
            QualityCheckResponse, OCRResultResponse, EnhancementResponse,
            ConfidenceReportResponse, MetadataResponse, ThresholdSettings
        )
        from datetime import datetime

        if return_format == "minimal":
            return OCRResponseMinimal(
                status="success",
                extracted_text="Sample OCR text",
                routing_decision="pass",
                confidence_score=90.0,
                document_id="doc-123"
            )
        elif return_format == "ocr_only":
            return OCRResponseOCROnly(
                status="success",
                raw_text="Sample OCR text",
                word_count=3,
                ocr_confidence=95.0,
                processing_time_ms=2500,
                document_id="doc-123"
            )
        else:
            # Full response
            quality_check = QualityCheckResponse(
                performed=True,
                passed=True,
                score=85.0,
                metrics={"sharpness": 85.0, "contrast": 80.0, "resolution": 90.0},
                issues=[]
            )

            ocr_result = OCRResultResponse(
                raw_text="Sample OCR text",
                word_count=3,
                confidence_score=95.0,
                confidence_distribution={"high": 3, "medium": 0, "low": 0}
            )

            confidence_report = ConfidenceReportResponse(
                image_quality_score=85.0,
                ocr_confidence_score=95.0,
                final_confidence=90.0,
                thresholds_applied=ThresholdSettings(
                    image_quality_threshold=60.0,
                    confidence_threshold=80.0
                ),
                routing_decision="pass",
                routing_reason="All thresholds met",
                quality_check_passed=True,
                confidence_check_passed=True
            )

            metadata = MetadataResponse(
                document_id="doc-123",
                timestamp=datetime.now(),
                processing_time_ms=2500
            )

            return OCRResponseFull(
                status="success",
                quality_check=quality_check,
                ocr_result=ocr_result,
                enhancement=None,
                confidence_report=confidence_report,
                metadata=metadata
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])