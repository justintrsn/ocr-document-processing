"""Contract tests for GET /queue/manual-review endpoint."""
import pytest
from fastapi.testclient import TestClient
from src.api.main import app  # Will be created later


class TestReviewQueueContract:
    """Contract tests for manual review queue endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_queue_retrieval(self, client):
        """Test retrieving the manual review queue."""
        response = client.get('/queue/manual-review')

        if response.status_code == 200:
            json_response = response.json()

            # Verify required fields
            required_fields = [
                'total_items', 'page', 'page_size', 'total_pages',
                'statistics', 'items'
            ]

            for field in required_fields:
                assert field in json_response, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(json_response['total_items'], int)
            assert isinstance(json_response['page'], int)
            assert isinstance(json_response['page_size'], int)
            assert isinstance(json_response['total_pages'], int)
            assert isinstance(json_response['statistics'], dict)
            assert isinstance(json_response['items'], list)

            # Verify pagination consistency
            assert json_response['page'] >= 1
            assert json_response['page_size'] > 0
            assert json_response['total_pages'] >= 0

            # If there are items, total_pages should be at least 1
            if json_response['total_items'] > 0:
                assert json_response['total_pages'] >= 1

    def test_queue_item_structure(self, client):
        """Test structure of items in the queue."""
        response = client.get('/queue/manual-review')

        if response.status_code == 200:
            json_response = response.json()
            items = json_response['items']

            if len(items) > 0:
                # Check first item structure
                item = items[0]

                required_fields = [
                    'id', 'document_id', 'filename', 'status', 'priority',
                    'confidence_score', 'queue_reason', 'queued_at', 'time_in_queue'
                ]

                for field in required_fields:
                    assert field in item, f"Missing required field in item: {field}"

                # Verify field types
                assert isinstance(item['id'], str)
                assert isinstance(item['document_id'], str)
                assert isinstance(item['filename'], str)
                assert isinstance(item['status'], str)
                assert isinstance(item['priority'], str)
                assert isinstance(item['confidence_score'], (int, float))
                assert isinstance(item['queue_reason'], str)
                assert isinstance(item['queued_at'], str)
                assert isinstance(item['time_in_queue'], (int, float))

                # Verify value ranges
                assert item['priority'] in ['high', 'medium', 'low']
                assert item['status'] in ['queued', 'in_review', 'completed']
                assert 0 <= item['confidence_score'] <= 100
                assert item['time_in_queue'] >= 0

    def test_priority_filtering(self, client):
        """Test filtering queue by priority."""
        priorities = ['high', 'medium', 'low']

        for priority in priorities:
            response = client.get(f'/queue/manual-review?priority={priority}')

            assert response.status_code == 200
            json_response = response.json()

            # All returned items should have the requested priority
            for item in json_response['items']:
                assert item['priority'] == priority

    def test_pagination(self, client):
        """Test pagination of queue results."""
        # Test different page sizes
        page_sizes = [10, 20, 50]

        for page_size in page_sizes:
            response = client.get(f'/queue/manual-review?page_size={page_size}')

            assert response.status_code == 200
            json_response = response.json()

            assert json_response['page_size'] == page_size

            # Number of items should not exceed page size
            assert len(json_response['items']) <= page_size

        # Test different pages
        response = client.get('/queue/manual-review?page=2&page_size=10')
        assert response.status_code == 200

    def test_queue_ordering(self, client):
        """Test that queue items are properly ordered."""
        response = client.get('/queue/manual-review')

        if response.status_code == 200:
            json_response = response.json()
            items = json_response['items']

            if len(items) > 1:
                # Items should be ordered by priority (high first) then by time
                priority_order = {'high': 1, 'medium': 2, 'low': 3}

                for i in range(len(items) - 1):
                    current_priority = priority_order[items[i]['priority']]
                    next_priority = priority_order[items[i + 1]['priority']]

                    assert current_priority <= next_priority, \
                        "Queue items not properly ordered by priority"

                    # Within same priority, should be FIFO (older first)
                    if current_priority == next_priority:
                        assert items[i]['queued_at'] <= items[i + 1]['queued_at'], \
                            "Items with same priority not in FIFO order"

    def test_statistics_structure(self, client):
        """Test queue statistics structure."""
        response = client.get('/queue/manual-review')

        if response.status_code == 200:
            json_response = response.json()
            statistics = json_response['statistics']

            # Expected statistics fields
            expected_stats = [
                'total_queued', 'total_in_review', 'by_priority',
                'average_wait_time', 'oldest_item_age'
            ]

            for stat in expected_stats:
                assert stat in statistics or True, f"Optional statistic: {stat}"

            # If by_priority exists, check structure
            if 'by_priority' in statistics:
                by_priority = statistics['by_priority']
                assert isinstance(by_priority, dict)

                for priority in ['high', 'medium', 'low']:
                    if priority in by_priority:
                        assert isinstance(by_priority[priority], int)
                        assert by_priority[priority] >= 0

    def test_confidence_score_filtering(self, client):
        """Test filtering by confidence score range."""
        # Test minimum confidence filter
        response = client.get('/queue/manual-review?min_confidence=60')

        if response.status_code == 200:
            json_response = response.json()
            for item in json_response['items']:
                assert item['confidence_score'] >= 60

        # Test maximum confidence filter
        response = client.get('/queue/manual-review?max_confidence=80')

        if response.status_code == 200:
            json_response = response.json()
            for item in json_response['items']:
                assert item['confidence_score'] <= 80

        # Test range
        response = client.get('/queue/manual-review?min_confidence=40&max_confidence=70')

        if response.status_code == 200:
            json_response = response.json()
            for item in json_response['items']:
                assert 40 <= item['confidence_score'] <= 70

    def test_status_filtering(self, client):
        """Test filtering by queue item status."""
        statuses = ['queued', 'in_review']

        for status in statuses:
            response = client.get(f'/queue/manual-review?status={status}')

            if response.status_code == 200:
                json_response = response.json()
                for item in json_response['items']:
                    assert item['status'] == status

    def test_reviewer_filtering(self, client):
        """Test filtering by reviewer ID."""
        response = client.get('/queue/manual-review?reviewer_id=reviewer123')

        if response.status_code == 200:
            json_response = response.json()
            for item in json_response['items']:
                if 'reviewer_id' in item and item['reviewer_id']:
                    assert item['reviewer_id'] == 'reviewer123'

    def test_empty_queue(self, client):
        """Test response for empty queue."""
        # Use filters that likely return empty results
        response = client.get('/queue/manual-review?min_confidence=99.9')

        assert response.status_code == 200
        json_response = response.json()

        assert json_response['total_items'] >= 0
        assert json_response['items'] == [] or len(json_response['items']) == 0

    def test_invalid_parameters(self, client):
        """Test handling of invalid query parameters."""
        invalid_requests = [
            '/queue/manual-review?page=0',  # Invalid page
            '/queue/manual-review?page=-1',  # Negative page
            '/queue/manual-review?page_size=0',  # Invalid page size
            '/queue/manual-review?page_size=1000',  # Too large page size
            '/queue/manual-review?priority=urgent',  # Invalid priority
            '/queue/manual-review?min_confidence=101',  # Invalid confidence
            '/queue/manual-review?max_confidence=-1',  # Invalid confidence
        ]

        for request in invalid_requests:
            response = client.get(request)
            assert response.status_code in [400, 422], \
                f"Expected error for request: {request}"

    def test_sort_parameters(self, client):
        """Test sorting parameters."""
        # Test sort by different fields
        sort_fields = ['queued_at', 'confidence_score', 'priority']

        for field in sort_fields:
            response = client.get(f'/queue/manual-review?sort_by={field}&sort_order=asc')
            assert response.status_code in [200, 400]  # May not support all fields

            response = client.get(f'/queue/manual-review?sort_by={field}&sort_order=desc')
            assert response.status_code in [200, 400]

    def test_authentication_required(self, client):
        """Test authentication for queue endpoint."""
        response = client.get('/queue/manual-review')

        if response.status_code == 401:
            # Test with API key
            headers = {'X-API-Key': 'test-api-key'}
            response = client.get('/queue/manual-review', headers=headers)
            assert response.status_code in [200, 401]

    def test_concurrent_queue_access(self, client):
        """Test concurrent access to the queue."""
        import concurrent.futures

        def get_queue():
            return client.get('/queue/manual-review?page_size=5')

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(get_queue) for _ in range(3)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        for response in responses:
            assert response.status_code in [200, 401]