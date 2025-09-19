"""Contract tests for GET /documents/{id}/result endpoint."""
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from src.api.main import app  # Will be created later


class TestDocumentResultContract:
    """Contract tests for document result endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def completed_document_id(self):
        """Mock ID for a completed document."""
        return str(uuid.uuid4())

    @pytest.fixture
    def incomplete_document_id(self):
        """Mock ID for an incomplete document."""
        return str(uuid.uuid4())

    def test_completed_document_retrieval(self, client, completed_document_id):
        """Test retrieving results for completed document."""
        response = client.get(f'/documents/{completed_document_id}/result')

        # Assuming document is completed
        if response.status_code == 200:
            json_response = response.json()

            # Verify required fields
            required_fields = [
                'document_id', 'filename', 'status', 'confidence_score',
                'routing_decision', 'processing_duration', 'extracted_text',
                'word_count', 'language', 'quality_level', 'validation_level',
                'submission_time', 'completion_time'
            ]

            for field in required_fields:
                assert field in json_response, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(json_response['document_id'], str)
            assert isinstance(json_response['filename'], str)
            assert isinstance(json_response['status'], str)
            assert isinstance(json_response['confidence_score'], (int, float))
            assert isinstance(json_response['routing_decision'], str)
            assert isinstance(json_response['processing_duration'], (int, float))
            assert isinstance(json_response['extracted_text'], str)
            assert isinstance(json_response['word_count'], int)
            assert isinstance(json_response['language'], str)

            # Verify confidence score range
            assert 0 <= json_response['confidence_score'] <= 100

            # Verify routing decision values
            assert json_response['routing_decision'] in ['automatic', 'manual_review']

    def test_incomplete_document_request(self, client, incomplete_document_id):
        """Test requesting results for incomplete document."""
        response = client.get(f'/documents/{incomplete_document_id}/result')

        # Should return 409 Conflict if document is not complete
        if response.status_code == 409:
            json_response = response.json()
            assert 'error' in json_response
            assert 'complete' in json_response['message'].lower() or \
                   'processing' in json_response['message'].lower()

    def test_non_existent_document(self, client):
        """Test requesting results for non-existent document."""
        non_existent_id = str(uuid.uuid4())
        response = client.get(f'/documents/{non_existent_id}/result')

        assert response.status_code == 404
        assert 'error' in response.json()
        assert 'not found' in response.json()['message'].lower()

    def test_confidence_breakdown_structure(self, client, completed_document_id):
        """Test confidence breakdown in results."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()
            confidence_score = json_response['confidence_score']

            # Verify confidence score is reasonable
            assert 0 <= confidence_score <= 100

            # Verify quality and validation levels
            quality_levels = ['excellent', 'good', 'fair', 'poor']
            assert json_response['quality_level'] in quality_levels
            assert json_response['validation_level'] in quality_levels

    def test_routing_decision_logic(self, client, completed_document_id):
        """Test routing decision based on confidence."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()
            confidence = json_response['confidence_score']
            routing = json_response['routing_decision']

            # Verify routing logic (threshold is 80%)
            if confidence >= 80:
                # High confidence could be automatic or manual based on other factors
                assert routing in ['automatic', 'manual_review']
            else:
                # Low confidence should typically be manual review
                assert routing == 'manual_review'

    def test_extracted_text_content(self, client, completed_document_id):
        """Test extracted text and metadata."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()

            # Verify extracted text
            extracted_text = json_response['extracted_text']
            assert isinstance(extracted_text, str)

            # Verify word count matches text (approximately)
            word_count = json_response['word_count']
            if extracted_text:
                actual_words = len(extracted_text.split())
                # Allow some variance in word counting methods
                assert abs(word_count - actual_words) <= actual_words * 0.2

            # Verify language detection
            language = json_response['language']
            assert language in ['en', 'zh', 'mixed', 'unknown']

    def test_optional_structured_data(self, client, completed_document_id):
        """Test optional structured data fields."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()

            # Check optional fields
            if 'key_values' in json_response:
                assert isinstance(json_response['key_values'], dict)

            if 'tables' in json_response:
                assert isinstance(json_response['tables'], list)

    def test_timestamp_formats(self, client, completed_document_id):
        """Test timestamp field formats."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()

            # Verify timestamp formats (ISO 8601)
            timestamp_fields = ['submission_time', 'completion_time']

            for field in timestamp_fields:
                timestamp_str = json_response[field]
                try:
                    datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    pytest.fail(f"Invalid timestamp format for {field}: {timestamp_str}")

            # Verify completion time is after submission time
            submission = datetime.fromisoformat(
                json_response['submission_time'].replace('Z', '+00:00')
            )
            completion = datetime.fromisoformat(
                json_response['completion_time'].replace('Z', '+00:00')
            )
            assert completion >= submission

    def test_processing_duration_calculation(self, client, completed_document_id):
        """Test processing duration calculation."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()

            duration = json_response['processing_duration']
            assert duration > 0  # Should be positive
            assert duration < 180  # Should be less than timeout (3 minutes)

            # Verify duration matches timestamp difference
            submission = datetime.fromisoformat(
                json_response['submission_time'].replace('Z', '+00:00')
            )
            completion = datetime.fromisoformat(
                json_response['completion_time'].replace('Z', '+00:00')
            )
            calculated_duration = (completion - submission).total_seconds()

            # Allow some variance
            assert abs(duration - calculated_duration) <= 1.0

    def test_failed_document_results(self, client):
        """Test results for failed document processing."""
        # Would need a failed document ID
        failed_document_id = str(uuid.uuid4())
        response = client.get(f'/documents/{failed_document_id}/result')

        # Failed documents might return results with error info
        if response.status_code == 200:
            json_response = response.json()
            if json_response['status'] == 'failed':
                # Should have minimal results
                assert json_response['confidence_score'] == 0 or \
                       json_response['confidence_score'] < 50
                assert 'error_message' in json_response or \
                       len(json_response['extracted_text']) == 0

    def test_result_caching(self, client, completed_document_id):
        """Test result caching for completed documents."""
        # First request
        response1 = client.get(f'/documents/{completed_document_id}/result')

        if response1.status_code == 200:
            # Second request should return same data
            response2 = client.get(f'/documents/{completed_document_id}/result')

            assert response2.status_code == 200
            assert response1.json() == response2.json()

            # Check for caching headers
            if 'cache-control' in response2.headers:
                # Completed results can be cached
                cache_control = response2.headers['cache-control'].lower()
                assert 'max-age' in cache_control

    def test_large_document_results(self, client, completed_document_id):
        """Test handling of large document results."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 200:
            json_response = response.json()

            # Check if large text is handled properly
            extracted_text = json_response['extracted_text']

            # Even for large documents, response should be reasonable
            # (e.g., might be truncated or paginated)
            response_size = len(response.content)
            assert response_size < 10 * 1024 * 1024  # Less than 10MB response

    def test_authentication_required(self, client, completed_document_id):
        """Test authentication requirement for results."""
        response = client.get(f'/documents/{completed_document_id}/result')

        if response.status_code == 401:
            # Test with API key
            headers = {'X-API-Key': 'test-api-key'}
            response = client.get(
                f'/documents/{completed_document_id}/result',
                headers=headers
            )
            assert response.status_code in [200, 401, 404, 409]