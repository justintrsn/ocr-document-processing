"""
Tests for OCR Service using OBS URLs

This test suite covers:
- Processing documents stored in OBS using signed URLs
- Direct API calls using the 'url' field
- OBS object listing and metadata retrieval
- Batch processing of multiple OBS documents
- Signed URL generation and validation
- OBS bucket operations (upload, delete, check existence)

Use case: Testing OCR functionality with OBS-hosted documents (production scenario)
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.services.ocr_service import HuaweiOCRService
from src.services.obs_service import OBSService
from src.models.ocr_models import OCRResponse


class TestOCRWithOBS:
    """Test OCR service with OBS integration - URL mode"""

    @pytest.fixture
    def obs_service(self):
        """Create OBS service instance with mocked client"""
        with patch('src.services.obs_service.ObsClient') as mock_obs_client:
            service = OBSService()
            service.obs_client = mock_obs_client
            return service

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
            return HuaweiOCRService()

    @pytest.fixture
    def sample_ocr_response(self):
        """Sample OCR response data"""
        return {
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
                },
                "kv_result": {
                    "kv_block_count": 1,
                    "kv_block_list": [
                        {
                            "key": "Patient Name",
                            "value": "John Doe",
                            "words_block_count": 1,
                            "words_block_list": []
                        }
                    ]
                }
            }]
        }

    def test_list_obs_objects(self, obs_service):
        """Test listing objects from OBS"""
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = Mock()
        mock_response.body.contents = [
            Mock(key='OCR/document1.jpg', size=1024, lastModified='2025-01-18T10:00:00', etag='abc123'),
            Mock(key='OCR/folder/', size=0, lastModified='2025-01-18T09:00:00', etag='def456'),
            Mock(key='OCR/document2.pdf', size=2048, lastModified='2025-01-18T11:00:00', etag='ghi789')
        ]

        obs_service.obs_client.listObjects.return_value = mock_response

        # Test listing
        objects = obs_service.list_objects(prefix="OCR/")

        # Verify results (should exclude folders)
        assert len(objects) == 2
        assert objects[0]['key'] == 'OCR/document1.jpg'
        assert objects[0]['size'] == 1024
        assert objects[1]['key'] == 'OCR/document2.pdf'

    def test_list_obs_folders(self, obs_service):
        """Test listing folders from OBS"""
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = Mock()
        mock_response.body.commonPrefixes = [
            Mock(prefix='OCR/medical/'),
            Mock(prefix='OCR/invoices/'),
            Mock(prefix='OCR/contracts/')
        ]

        obs_service.obs_client.listObjects.return_value = mock_response

        # Test listing folders
        folders = obs_service.list_folders(prefix="OCR/")

        # Verify results
        assert len(folders) == 3
        assert 'OCR/medical' in folders
        assert 'OCR/invoices' in folders
        assert 'OCR/contracts' in folders

    def test_get_signed_url(self, obs_service):
        """Test generating signed URL for OBS object"""
        # Mock response
        mock_response = Mock()
        mock_response.signedUrl = "https://bucket.obs.region.com/OCR/document.jpg?signature=xyz"

        obs_service.obs_client.createSignedUrl.return_value = mock_response

        # Test generating URL
        url = obs_service.get_signed_url("OCR/document.jpg", expires_in=300)

        # Verify
        assert url == "https://bucket.obs.region.com/OCR/document.jpg?signature=xyz"
        obs_service.obs_client.createSignedUrl.assert_called_once()

    @patch('src.services.ocr_service.requests.post')
    def test_process_document_from_obs_url(self, mock_post, ocr_service, sample_ocr_response):
        """Test processing document using OBS URL"""
        # Mock IAM token response
        mock_token_response = Mock()
        mock_token_response.status_code = 201
        mock_token_response.headers = {'X-Subject-Token': 'test_token'}

        # Mock OCR response
        mock_ocr_response = Mock()
        mock_ocr_response.status_code = 200
        mock_ocr_response.json.return_value = sample_ocr_response

        mock_post.side_effect = [mock_token_response, mock_ocr_response]

        # Test processing with URL
        test_url = "https://bucket.obs.region.com/OCR/document.jpg?signature=xyz"
        result = ocr_service.process_document(image_url=test_url)

        # Verify
        assert isinstance(result, OCRResponse)
        assert len(result.result) == 1
        assert len(result.result[0].ocr_result.words_block_list) == 2

        # Check extracted text
        text = ocr_service.extract_text_from_response(result)
        assert "Medical Certificate" in text
        assert "Patient Name: John Doe" in text

        # Check confidence
        confidence = ocr_service.get_average_confidence(result)
        assert confidence > 0.95

    def test_check_object_exists(self, obs_service):
        """Test checking if object exists in OBS"""
        # Mock existing object
        mock_response = Mock()
        mock_response.status = 200
        obs_service.obs_client.getObjectMetadata.return_value = mock_response

        # Test
        exists = obs_service.check_object_exists("OCR/document.jpg")
        assert exists is True

        # Mock non-existing object
        mock_response.status = 404
        obs_service.obs_client.getObjectMetadata.return_value = mock_response

        exists = obs_service.check_object_exists("OCR/nonexistent.jpg")
        assert exists is False

    def test_get_object_metadata(self, obs_service):
        """Test getting object metadata from OBS"""
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = Mock()
        mock_response.body.contentLength = 1024
        mock_response.body.contentType = 'image/jpeg'
        mock_response.body.lastModified = '2025-01-18T10:00:00'
        mock_response.body.etag = 'abc123'

        obs_service.obs_client.getObjectMetadata.return_value = mock_response

        # Test
        metadata = obs_service.get_object_metadata("OCR/document.jpg")

        # Verify
        assert metadata['key'] == "OCR/document.jpg"
        assert metadata['size'] == 1024
        assert metadata['content_type'] == 'image/jpeg'
        assert metadata['etag'] == 'abc123'

    @patch('src.services.ocr_service.requests.post')
    def test_process_batch_from_obs(self, mock_post, ocr_service, obs_service, sample_ocr_response):
        """Test batch processing of documents from OBS"""
        # Mock OBS listing
        mock_list_response = Mock()
        mock_list_response.status = 200
        mock_list_response.body = Mock()
        mock_list_response.body.contents = [
            Mock(key='OCR/doc1.jpg', size=1024, lastModified='2025-01-18T10:00:00', etag='abc'),
            Mock(key='OCR/doc2.jpg', size=2048, lastModified='2025-01-18T11:00:00', etag='def')
        ]
        obs_service.obs_client.listObjects.return_value = mock_list_response

        # Mock signed URL generation
        mock_url_response = Mock()
        mock_url_response.signedUrl = "https://signed.url/document.jpg"
        obs_service.obs_client.createSignedUrl.return_value = mock_url_response

        # Mock OCR responses
        mock_token_response = Mock()
        mock_token_response.status_code = 201
        mock_token_response.headers = {'X-Subject-Token': 'test_token'}

        mock_ocr_response = Mock()
        mock_ocr_response.status_code = 200
        mock_ocr_response.json.return_value = sample_ocr_response

        mock_post.side_effect = [mock_token_response, mock_ocr_response] * 2

        # Get objects and process
        objects = obs_service.list_objects(prefix="OCR/")
        results = []

        for obj in objects:
            url = obs_service.get_signed_url(obj['key'])
            response = ocr_service.process_document(image_url=url)
            results.append({
                'key': obj['key'],
                'confidence': ocr_service.get_average_confidence(response)
            })

        # Verify
        assert len(results) == 2
        assert results[0]['key'] == 'OCR/doc1.jpg'
        assert results[0]['confidence'] > 0.9

    def test_upload_file_to_obs(self, obs_service, tmp_path):
        """Test uploading file to OBS"""
        # Create test file
        test_file = tmp_path / "test_document.jpg"
        test_file.write_bytes(b"test image content")

        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        obs_service.obs_client.putObject.return_value = mock_response

        # Test upload
        success = obs_service.upload_file(test_file, "OCR/uploads/test_document.jpg")

        # Verify
        assert success is True
        obs_service.obs_client.putObject.assert_called_once()

    def test_delete_object_from_obs(self, obs_service):
        """Test deleting object from OBS"""
        # Mock response
        mock_response = Mock()
        mock_response.status = 204
        obs_service.obs_client.deleteObject.return_value = mock_response

        # Test delete
        success = obs_service.delete_object("OCR/old_document.jpg")

        # Verify
        assert success is True
        obs_service.obs_client.deleteObject.assert_called_once_with(
            bucketName=obs_service.bucket_name,
            objectKey="OCR/old_document.jpg"
        )