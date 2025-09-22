"""
Contract tests for history retrieval endpoint
Tests GET /api/v1/ocr/history/{document_id}
"""

import pytest
from fastapi.testclient import TestClient
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import io
from PIL import Image
import uuid


@pytest.fixture
def client():
    """Create test client"""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def sample_document():
    """Create a sample document"""
    img = Image.new('RGB', (100, 100), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


@pytest.fixture
def setup_history_record():
    """Setup a history record in database"""
    from src.db.init_db import HistoryDatabase

    db = HistoryDatabase()
    history_id = str(uuid.uuid4())
    document_id = f"test_doc_{uuid.uuid4().hex[:8]}"

    # Add a history record
    db.add_history(
        history_id=history_id,
        document_id=document_id,
        file_format="PNG",
        file_name="test_image.png",
        file_size_bytes=1024,
        processing_time_ms=1500,
        success=True,
        result_summary="OCR completed successfully"
    )

    return document_id


class TestHistoryEndpointContract:
    """Test GET /api/v1/ocr/history/{document_id} contract compliance"""

    def test_history_retrieval_success(self, client, setup_history_record):
        """Test successful history retrieval"""
        document_id = setup_history_record

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        assert response.status_code == 200
        result = response.json()

        # Verify response schema
        assert "document_id" in result
        assert "processing_history" in result
        assert "metadata" in result

        history = result["processing_history"]
        assert "processed_at" in history
        assert "file_format" in history
        assert "file_name" in history
        assert "file_size_bytes" in history
        assert "processing_time_ms" in history
        assert "success" in history
        assert "result_summary" in history

    def test_history_not_found_404(self, client):
        """Test 404 for non-existent document"""
        non_existent_id = "doc_" + uuid.uuid4().hex[:8]

        response = client.get(f"/api/v1/ocr/history/{non_existent_id}")

        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "HISTORY_NOT_FOUND" in error_response.get("error_code", "")

    def test_history_expired_document_404(self, client):
        """Test 404 for expired documents (>7 days old)"""
        from src.db.init_db import HistoryDatabase
        import sqlite3

        db = HistoryDatabase()
        history_id = str(uuid.uuid4())
        document_id = f"expired_doc_{uuid.uuid4().hex[:8]}"

        # Manually insert an expired record
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Set processed_at to 8 days ago and expires_at to 1 day ago
            cursor.execute("""
                INSERT INTO processing_history (
                    history_id, document_id, file_format, file_name,
                    file_size_bytes, processing_time_ms, success,
                    processed_at, expires_at, result_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                history_id, document_id, "PNG", "old_image.png",
                1024, 1000, True,
                (datetime.now() - timedelta(days=8)).isoformat(),
                (datetime.now() - timedelta(days=1)).isoformat(),
                "Old OCR result"
            ))
            conn.commit()

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        # Should return 404 for expired document
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "expired" in error_response["error"].lower() or "not found" in error_response["error"].lower()

    def test_history_response_schema_validation(self, client, setup_history_record):
        """Test that response matches expected schema"""
        document_id = setup_history_record

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        assert response.status_code == 200
        result = response.json()

        # Validate data types
        assert isinstance(result["document_id"], str)
        assert isinstance(result["processing_history"], dict)
        assert isinstance(result["metadata"], dict)

        history = result["processing_history"]
        assert isinstance(history["file_size_bytes"], int)
        assert isinstance(history["processing_time_ms"], (int, float))
        assert isinstance(history["success"], bool)

        # Validate ISO format timestamps
        try:
            datetime.fromisoformat(history["processed_at"])
        except ValueError:
            pytest.fail("processed_at is not in valid ISO format")

    def test_history_with_error_details(self, client):
        """Test history retrieval for failed processing"""
        from src.db.init_db import HistoryDatabase

        db = HistoryDatabase()
        history_id = str(uuid.uuid4())
        document_id = f"failed_doc_{uuid.uuid4().hex[:8]}"

        # Add a failed processing record
        db.add_history(
            history_id=history_id,
            document_id=document_id,
            file_format="PDF",
            file_name="corrupted.pdf",
            file_size_bytes=2048000,
            processing_time_ms=500,
            success=False,
            error_code="PDF_CORRUPTED",
            result_summary="Failed to process PDF: File corrupted"
        )

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        assert response.status_code == 200
        result = response.json()

        history = result["processing_history"]
        assert history["success"] is False
        assert "error_code" in history
        assert history["error_code"] == "PDF_CORRUPTED"
        assert "Failed" in history["result_summary"]

    def test_history_endpoint_headers(self, client, setup_history_record):
        """Test response headers for history endpoint"""
        document_id = setup_history_record

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        assert response.status_code == 200

        # Check content type
        assert response.headers["content-type"] == "application/json"

        # Should have cache control headers
        if "cache-control" in response.headers:
            assert "no-cache" in response.headers["cache-control"] or \
                   "no-store" in response.headers["cache-control"]

    def test_history_invalid_document_id_format(self, client):
        """Test handling of invalid document ID format"""
        invalid_ids = [
            "../etc/passwd",  # Path traversal attempt
            "'; DROP TABLE processing_history;--",  # SQL injection attempt
            "",  # Empty ID
            "a" * 1000,  # Very long ID
        ]

        for invalid_id in invalid_ids:
            response = client.get(f"/api/v1/ocr/history/{invalid_id}")

            # Should handle gracefully with 400 or 404
            assert response.status_code in [400, 404]

            if response.status_code == 400:
                error_response = response.json()
                assert "error" in error_response

    def test_history_recent_processing(self, client, sample_document):
        """Test that recent processing creates retrievable history"""
        # First, process a document
        document_id = f"new_doc_{uuid.uuid4().hex[:8]}"

        process_request = {
            "source": {
                "type": "file",
                "file": sample_document
            },
            "processing_options": {
                "enable_ocr": True,
                "track_history": True,
                "document_id": document_id
            }
        }

        # Process the document
        process_response = client.post("/api/v1/ocr", json=process_request)

        # If processing succeeded, history should be available
        if process_response.status_code == 200:
            # Retrieve history
            history_response = client.get(f"/api/v1/ocr/history/{document_id}")

            # History should be available immediately
            assert history_response.status_code == 200

            result = history_response.json()
            assert result["document_id"] == document_id
            assert result["processing_history"]["file_format"] in ["PNG", "JPG", "JPEG"]

    def test_history_metadata_fields(self, client, setup_history_record):
        """Test that metadata contains expected fields"""
        document_id = setup_history_record

        response = client.get(f"/api/v1/ocr/history/{document_id}")

        assert response.status_code == 200
        result = response.json()

        metadata = result["metadata"]

        # Expected metadata fields
        expected_fields = [
            "expires_at",
            "days_until_expiry",
            "retrievable_until"
        ]

        for field in expected_fields:
            assert field in metadata, f"Missing metadata field: {field}"

        # Validate expiry is within 7 days
        assert metadata["days_until_expiry"] <= 7
        assert metadata["days_until_expiry"] >= 0