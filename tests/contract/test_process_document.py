"""Contract tests for POST /documents/process endpoint."""
import io
import pytest
from fastapi.testclient import TestClient
from src.api.main import app  # Will be created later


class TestProcessDocumentContract:
    """Contract tests for document processing endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def valid_document(self):
        """Create a valid test document."""
        # Create a small valid JPEG image
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        return img_bytes

    @pytest.fixture
    def oversized_document(self):
        """Create an oversized document (>10MB)."""
        # Create a large byte stream
        return io.BytesIO(b'x' * (11 * 1024 * 1024))  # 11MB

    def test_valid_document_upload(self, client, valid_document):
        """Test uploading a valid document."""
        files = {
            'file': ('test_document.jpg', valid_document, 'image/jpeg')
        }
        data = {
            'priority': 'medium'
        }

        response = client.post('/documents/process', files=files, data=data)

        assert response.status_code == 202  # Accepted
        assert 'document_id' in response.json()
        assert 'status' in response.json()
        assert response.json()['status'] == 'pending'
        assert 'message' in response.json()

    def test_invalid_format_rejection(self, client):
        """Test rejection of invalid file format."""
        files = {
            'file': ('test.txt', io.BytesIO(b'text content'), 'text/plain')
        }

        response = client.post('/documents/process', files=files)

        assert response.status_code == 400  # Bad Request
        assert 'error' in response.json()
        assert 'format' in response.json()['message'].lower()

    def test_file_size_limit(self, client, oversized_document):
        """Test rejection of oversized file (>10MB)."""
        files = {
            'file': ('large_document.jpg', oversized_document, 'image/jpeg')
        }

        response = client.post('/documents/process', files=files)

        assert response.status_code == 400  # Bad Request
        assert 'error' in response.json()
        assert 'size' in response.json()['message'].lower()
        assert '10MB' in response.json()['message'] or '10' in response.json()['message']

    def test_missing_file(self, client):
        """Test request without file attachment."""
        response = client.post('/documents/process', data={'priority': 'high'})

        assert response.status_code == 400  # Bad Request
        assert 'error' in response.json()
        assert 'file' in response.json()['message'].lower()

    def test_response_schema_validation(self, client, valid_document):
        """Test that response matches expected schema."""
        files = {
            'file': ('test.jpg', valid_document, 'image/jpeg')
        }

        response = client.post('/documents/process', files=files)

        assert response.status_code == 202

        # Validate response schema
        json_response = response.json()
        required_fields = ['document_id', 'status', 'message']
        for field in required_fields:
            assert field in json_response, f"Missing required field: {field}"

        # Validate field types
        assert isinstance(json_response['document_id'], str)
        assert isinstance(json_response['status'], str)
        assert isinstance(json_response['message'], str)

        # Optional field
        if 'estimated_completion' in json_response:
            assert isinstance(json_response['estimated_completion'], str)

    def test_supported_formats(self, client):
        """Test all supported document formats."""
        formats = [
            ('test.pdf', 'application/pdf'),
            ('test.jpg', 'image/jpeg'),
            ('test.jpeg', 'image/jpeg'),
            ('test.png', 'image/png'),
            ('test.tiff', 'image/tiff')
        ]

        for filename, content_type in formats:
            # Create appropriate test file
            if 'image' in content_type:
                from PIL import Image
                img = Image.new('RGB', (10, 10))
                file_bytes = io.BytesIO()
                format_name = filename.split('.')[-1].upper()
                if format_name == 'JPG':
                    format_name = 'JPEG'
                img.save(file_bytes, format=format_name)
                file_bytes.seek(0)
            else:
                # For PDF, create a minimal valid PDF
                file_bytes = io.BytesIO(b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n203\n%%EOF')

            files = {'file': (filename, file_bytes, content_type)}
            response = client.post('/documents/process', files=files)

            assert response.status_code == 202, f"Failed for format {filename}"

    def test_priority_levels(self, client, valid_document):
        """Test different priority levels."""
        priorities = ['high', 'medium', 'low']

        for priority in priorities:
            files = {
                'file': ('test.jpg', valid_document, 'image/jpeg')
            }
            data = {'priority': priority}

            valid_document.seek(0)  # Reset file pointer
            response = client.post('/documents/process', files=files, data=data)

            assert response.status_code == 202, f"Failed for priority {priority}"

    def test_invalid_priority(self, client, valid_document):
        """Test invalid priority value."""
        files = {
            'file': ('test.jpg', valid_document, 'image/jpeg')
        }
        data = {'priority': 'urgent'}  # Invalid priority

        response = client.post('/documents/process', files=files, data=data)

        # Should either accept with default priority or return 400
        assert response.status_code in [202, 400]

    def test_metadata_inclusion(self, client, valid_document):
        """Test including metadata with document."""
        files = {
            'file': ('test.jpg', valid_document, 'image/jpeg')
        }
        data = {
            'priority': 'medium',
            'metadata': '{"source": "scanner", "department": "finance"}'
        }

        response = client.post('/documents/process', files=files, data=data)

        assert response.status_code == 202

    def test_concurrent_uploads(self, client, valid_document):
        """Test handling of concurrent document uploads."""
        import concurrent.futures

        def upload_document():
            files = {
                'file': ('test.jpg', io.BytesIO(valid_document.getvalue()), 'image/jpeg')
            }
            return client.post('/documents/process', files=files)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_document) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All uploads should be accepted
        for response in responses:
            assert response.status_code == 202

        # All should have unique document IDs
        document_ids = [r.json()['document_id'] for r in responses]
        assert len(document_ids) == len(set(document_ids)), "Document IDs should be unique"

    def test_special_characters_in_filename(self, client, valid_document):
        """Test handling of special characters in filename."""
        special_filenames = [
            'test document.jpg',  # Space
            'test-document.jpg',  # Hyphen
            'test_document.jpg',  # Underscore
            'test.document.jpg',  # Multiple dots
            'tëst.jpg',          # Unicode
            '测试.jpg'            # Chinese characters
        ]

        for filename in special_filenames:
            valid_document.seek(0)
            files = {
                'file': (filename, valid_document, 'image/jpeg')
            }

            response = client.post('/documents/process', files=files)

            # Should handle gracefully
            assert response.status_code in [202, 400]

    def test_api_key_authentication(self, client, valid_document):
        """Test API key authentication if enabled."""
        files = {
            'file': ('test.jpg', valid_document, 'image/jpeg')
        }

        # Test without API key
        response = client.post('/documents/process', files=files)

        # If authentication is required, should return 401
        # If not required, should return 202
        assert response.status_code in [202, 401]

        if response.status_code == 401:
            # Test with API key
            headers = {'X-API-Key': 'test-api-key'}
            valid_document.seek(0)
            response = client.post('/documents/process', files=files, headers=headers)
            # With valid key, should accept or reject based on key validity
            assert response.status_code in [202, 401]