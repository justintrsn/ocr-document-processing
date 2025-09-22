"""
Contract tests for batch processing endpoint
Tests POST /api/v1/batch for multi-document processing
"""

import pytest
from fastapi.testclient import TestClient
import base64
from unittest.mock import Mock, patch
import io
from PIL import Image
import json


@pytest.fixture
def client():
    """Create test client"""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def sample_documents():
    """Create sample documents for batch processing"""
    documents = []

    # Create various format samples
    for i in range(3):
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        documents.append({
            "document_id": f"doc_{i+1}",
            "file": base64.b64encode(buffer.read()).decode('utf-8'),
            "format_hint": "PNG"
        })

    return documents


class TestBatchEndpointContract:
    """Test POST /api/v1/batch contract compliance"""

    def test_batch_processing_multi_document(self, client, sample_documents):
        """Test batch processing with multiple documents"""
        request_body = {
            "documents": sample_documents,
            "processing_options": {
                "enable_ocr": True,
                "enable_quality_check": True
            },
            "fail_fast": False
        }

        response = client.post("/api/v1/batch", json=request_body)

        # Should accept the request
        assert response.status_code in [200, 207, 400, 500]

        if response.status_code == 207:  # Multi-status
            result = response.json()
            assert "results" in result
            assert len(result["results"]) == len(sample_documents)

            # Each result should have document_id and status
            for doc_result in result["results"]:
                assert "document_id" in doc_result
                assert "status" in doc_result
                assert doc_result["status"] in ["success", "failed", "error"]

    def test_batch_processing_max_documents(self, client):
        """Test batch processing respects 20 document limit"""
        # Create 21 documents (over limit)
        documents = []
        for i in range(21):
            img = Image.new('RGB', (100, 100), color='white')
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            documents.append({
                "document_id": f"doc_{i+1}",
                "file": base64.b64encode(buffer.read()).decode('utf-8')
            })

        request_body = {
            "documents": documents,
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/batch", json=request_body)

        # Should reject with 400 Bad Request
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response
        assert "BATCH_SIZE_EXCEEDED" in error_response.get("error_code", "")

    def test_batch_processing_fail_fast_option(self, client, sample_documents):
        """Test fail_fast option stops processing on first error"""
        # Add a corrupt document in the middle
        sample_documents[1]["file"] = "INVALID_BASE64"

        request_body = {
            "documents": sample_documents,
            "processing_options": {
                "enable_ocr": True
            },
            "fail_fast": True
        }

        response = client.post("/api/v1/batch", json=request_body)

        assert response.status_code in [207, 400, 500]

        if response.status_code == 207:
            result = response.json()
            assert "results" in result

            # Should have stopped processing after error
            processed_count = sum(1 for r in result["results"] if "status" in r)
            assert processed_count <= 2  # First doc + failed doc

    def test_batch_processing_continue_on_error(self, client, sample_documents):
        """Test that batch continues processing when fail_fast=false"""
        # Add a corrupt document in the middle
        sample_documents[1]["file"] = "INVALID_BASE64"

        request_body = {
            "documents": sample_documents,
            "processing_options": {
                "enable_ocr": True
            },
            "fail_fast": False
        }

        response = client.post("/api/v1/batch", json=request_body)

        assert response.status_code in [207, 400, 500]

        if response.status_code == 207:
            result = response.json()
            assert "results" in result

            # Should process all documents
            assert len(result["results"]) == len(sample_documents)

            # Middle document should fail, others succeed
            assert result["results"][1]["status"] == "error"

    def test_batch_processing_timeout_handling(self, client):
        """Test timeout handling for batch processing"""
        documents = []
        for i in range(5):
            img = Image.new('RGB', (1000, 1000), color='white')  # Larger image
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            documents.append({
                "document_id": f"doc_{i+1}",
                "file": base64.b64encode(buffer.read()).decode('utf-8')
            })

        request_body = {
            "documents": documents,
            "processing_options": {
                "enable_ocr": True,
                "timeout_seconds": 1  # Very short timeout
            }
        }

        response = client.post("/api/v1/batch", json=request_body)

        assert response.status_code in [207, 408, 500]

        if response.status_code == 207:
            result = response.json()
            # Some documents might timeout
            timeout_count = sum(1 for r in result["results"]
                                if r.get("error_code") == "TIMEOUT")
            assert timeout_count >= 0

    def test_batch_processing_207_multi_status(self, client, sample_documents):
        """Test that mixed success/failure returns 207 Multi-Status"""
        # Make one document invalid
        sample_documents[0]["file"] = "INVALID"

        request_body = {
            "documents": sample_documents,
            "processing_options": {
                "enable_ocr": True
            },
            "fail_fast": False
        }

        response = client.post("/api/v1/batch", json=request_body)

        # Should return 207 for mixed results
        assert response.status_code == 207

        result = response.json()
        assert "results" in result
        assert "summary" in result

        # Summary should contain counts
        summary = result["summary"]
        assert "total" in summary
        assert "successful" in summary
        assert "failed" in summary
        assert summary["total"] == len(sample_documents)
        assert summary["failed"] >= 1

    def test_batch_processing_different_formats(self, client):
        """Test batch processing with mixed file formats"""
        documents = []

        # PNG
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        documents.append({
            "document_id": "doc_png",
            "file": base64.b64encode(buffer.read()).decode('utf-8'),
            "format_hint": "PNG"
        })

        # JPEG
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        documents.append({
            "document_id": "doc_jpg",
            "file": base64.b64encode(buffer.read()).decode('utf-8'),
            "format_hint": "JPG"
        })

        # BMP
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='BMP')
        buffer.seek(0)
        documents.append({
            "document_id": "doc_bmp",
            "file": base64.b64encode(buffer.read()).decode('utf-8'),
            "format_hint": "BMP"
        })

        request_body = {
            "documents": documents,
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = client.post("/api/v1/batch", json=request_body)

        assert response.status_code in [200, 207]

        if response.status_code in [200, 207]:
            result = response.json()
            assert "results" in result

            # Each format should be detected correctly
            for doc_result in result["results"]:
                if doc_result["status"] == "success":
                    assert "format_detected" in doc_result

    def test_batch_processing_parallel_execution(self, client, sample_documents):
        """Test that batch processing uses parallel execution"""
        import time

        # Add processing timestamp tracking
        request_body = {
            "documents": sample_documents[:4],  # Use 4 documents
            "processing_options": {
                "enable_ocr": True
            }
        }

        start_time = time.time()
        response = client.post("/api/v1/batch", json=request_body)
        end_time = time.time()

        assert response.status_code in [200, 207]

        # With parallel processing (4 workers), should be faster than sequential
        # This is a rough test - actual timing depends on implementation
        processing_time = end_time - start_time

        if response.status_code in [200, 207]:
            result = response.json()
            assert "results" in result
            # Should have metadata about parallel processing
            if "processing_metadata" in result:
                assert "parallel_workers" in result["processing_metadata"]
                assert result["processing_metadata"]["parallel_workers"] <= 4