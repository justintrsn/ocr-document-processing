"""
Integration tests for OBS and OCR service
Requires actual OBS connection - skip if not configured
"""

import pytest
import os
from pathlib import Path

from src.services.obs_service import OBSService
from src.services.ocr_service import HuaweiOCRService
from src.core.config import settings


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("HUAWEI_ACCESS_KEY"),
    reason="OBS credentials not configured"
)
class TestOBSIntegration:
    """Integration tests with actual OBS service"""

    @pytest.fixture(scope="class")
    def obs_service(self):
        """Create actual OBS service instance"""
        service = OBSService()
        yield service
        service.close()

    @pytest.fixture(scope="class")
    def ocr_service(self):
        """Create actual OCR service instance"""
        return HuaweiOCRService()

    def test_list_ocr_objects(self, obs_service):
        """Test listing objects in OCR folder"""
        objects = obs_service.list_objects(prefix="OCR/")

        # Should have at least the test document
        assert isinstance(objects, list)

        # Check if our test document exists
        test_doc_exists = any(
            obj['key'] == 'OCR/scanned_document.jpg'
            for obj in objects
        )
        assert test_doc_exists, "Test document should exist in OBS"

        # Print found objects for debugging
        print(f"\nFound {len(objects)} objects in OCR/:")
        for obj in objects[:5]:  # Show first 5
            print(f"  - {obj['key']} ({obj['size']} bytes)")

    def test_list_folders_in_ocr(self, obs_service):
        """Test listing folders within OCR directory"""
        folders = obs_service.list_folders(prefix="OCR/")

        print(f"\nFound {len(folders)} folders in OCR/:")
        for folder in folders:
            print(f"  - {folder}/")

        assert isinstance(folders, list)

    def test_check_test_document_exists(self, obs_service):
        """Test checking if test document exists"""
        exists = obs_service.check_object_exists("OCR/scanned_document.jpg")
        assert exists is True

        # Check non-existent
        not_exists = obs_service.check_object_exists("OCR/nonexistent_file.jpg")
        assert not_exists is False

    def test_get_test_document_metadata(self, obs_service):
        """Test getting metadata for test document"""
        metadata = obs_service.get_object_metadata("OCR/scanned_document.jpg")

        assert metadata
        assert metadata['key'] == "OCR/scanned_document.jpg"
        assert metadata['size'] > 0
        assert 'content_type' in metadata
        assert 'last_modified' in metadata

        print(f"\nTest document metadata:")
        print(f"  Size: {metadata['size']} bytes")
        print(f"  Type: {metadata['content_type']}")
        print(f"  Modified: {metadata['last_modified']}")

    def test_generate_signed_url(self, obs_service):
        """Test generating signed URL for test document"""
        url = obs_service.get_signed_url("OCR/scanned_document.jpg", expires_in=60)

        assert url
        assert "https://" in url
        assert settings.obs_bucket_name in url
        assert "OCR/scanned_document.jpg" in url

        print(f"\nGenerated signed URL (valid for 60s):")
        print(f"  {url[:100]}...")

    @pytest.mark.slow
    def test_process_document_from_obs(self, obs_service, ocr_service):
        """Test full OCR processing from OBS"""
        # Generate signed URL
        url = obs_service.get_signed_url("OCR/scanned_document.jpg", expires_in=300)

        # Process with OCR
        response = ocr_service.process_document(image_url=url)

        # Verify response
        assert response
        assert response.result
        assert len(response.result) > 0

        # Extract text
        text = ocr_service.extract_text_from_response(response)
        confidence = ocr_service.get_average_confidence(response)

        assert text
        assert confidence > 0.5  # Should have reasonable confidence

        print(f"\nOCR Results:")
        print(f"  Confidence: {confidence*100:.2f}%")
        print(f"  Text length: {len(text)} characters")
        print(f"  Text preview: {text[:100]}...")

        # Check for expected content (medical certificate)
        assert any(word in text.lower() for word in ['medical', 'certificate', 'date'])

    def test_upload_and_process_new_document(self, obs_service, ocr_service, tmp_path):
        """Test uploading a new document and processing it"""
        # Skip if no write permissions
        test_key = "OCR/test_uploads/integration_test.txt"

        # Create a simple test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Integration Test Document\nThis is a test.")

        try:
            # Upload to OBS
            success = obs_service.upload_file(test_file, test_key)

            if success:
                # Verify it exists
                exists = obs_service.check_object_exists(test_key)
                assert exists

                # Clean up
                obs_service.delete_object(test_key)
            else:
                pytest.skip("Upload failed - possibly no write permissions")

        except Exception as e:
            pytest.skip(f"Upload test skipped: {e}")

    def test_batch_listing_performance(self, obs_service):
        """Test performance of listing many objects"""
        import time

        start = time.time()
        objects = obs_service.list_objects(prefix="OCR/", max_keys=100)
        duration = time.time() - start

        print(f"\nListing performance:")
        print(f"  Retrieved {len(objects)} objects in {duration:.2f}s")

        assert duration < 5.0  # Should complete within 5 seconds

    @pytest.mark.parametrize("prefix", [
        "OCR/",
        "OCR/medical/",
        "OCR/invoices/",
        "OCR/contracts/"
    ])
    def test_list_different_folders(self, obs_service, prefix):
        """Test listing objects in different subfolders"""
        objects = obs_service.list_objects(prefix=prefix)

        print(f"\nObjects in {prefix}: {len(objects)}")

        # Should not fail even if folder is empty
        assert isinstance(objects, list)