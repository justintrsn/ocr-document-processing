"""Contract tests for GET /health endpoint."""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from src.api.main import app  # Will be created later


class TestHealthCheckContract:
    """Contract tests for health check endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_healthy_status(self, client):
        """Test health check when service is healthy."""
        response = client.get('/health')

        assert response.status_code == 200
        json_response = response.json()

        # Verify required fields
        required_fields = ['status', 'timestamp', 'version', 'services']

        for field in required_fields:
            assert field in json_response, f"Missing required field: {field}"

        # Verify status value
        assert json_response['status'] in ['healthy', 'degraded', 'unhealthy']

        # Verify timestamp format
        timestamp_str = json_response['timestamp']
        try:
            datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp_str}")

        # Verify version format
        assert isinstance(json_response['version'], str)
        assert len(json_response['version']) > 0

        # Verify services dictionary
        assert isinstance(json_response['services'], dict)

    def test_service_dependencies(self, client):
        """Test individual service status reporting."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()
            services = json_response['services']

            # Expected services based on architecture
            expected_services = [
                'database',
                'ocr_service',
                'validation_service',
                'queue_service',
                'storage'
            ]

            for service in expected_services:
                if service in services:
                    # Each service should report its status
                    status = services[service]
                    assert status in ['healthy', 'degraded', 'unhealthy', 'up', 'down']

    def test_degraded_status(self, client):
        """Test health check behavior when service is degraded."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()

            # If status is degraded, should still return 200
            if json_response['status'] == 'degraded':
                # Should indicate which services are problematic
                services = json_response['services']

                # At least one service should not be healthy
                unhealthy_services = [
                    name for name, status in services.items()
                    if status not in ['healthy', 'up']
                ]
                assert len(unhealthy_services) > 0

    def test_unhealthy_status(self, client):
        """Test health check when service is unhealthy."""
        response = client.get('/health')

        # Unhealthy service might return 503 Service Unavailable
        if response.status_code == 503:
            json_response = response.json()

            assert json_response['status'] == 'unhealthy'

            # Should indicate critical failures
            services = json_response['services']
            critical_failures = [
                name for name, status in services.items()
                if status in ['unhealthy', 'down']
            ]
            assert len(critical_failures) > 0

    def test_metrics_inclusion(self, client):
        """Test optional metrics in health response."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()

            # Metrics are optional
            if 'metrics' in json_response:
                metrics = json_response['metrics']
                assert isinstance(metrics, dict)

                # Possible metrics
                possible_metrics = [
                    'uptime', 'memory_usage', 'cpu_usage',
                    'queue_size', 'active_connections',
                    'processed_documents', 'error_rate'
                ]

                for metric in possible_metrics:
                    if metric in metrics:
                        # Verify metric value is reasonable
                        value = metrics[metric]
                        assert value is not None

                        if 'usage' in metric or 'rate' in metric:
                            # Percentages should be 0-100
                            if isinstance(value, (int, float)):
                                assert 0 <= value <= 100

                        elif metric == 'uptime':
                            # Uptime should be positive
                            assert value >= 0

    def test_response_time(self, client):
        """Test that health check responds quickly."""
        import time

        start_time = time.time()
        response = client.get('/health')
        end_time = time.time()

        response_time = end_time - start_time

        # Health check should be fast (less than 1 second)
        assert response_time < 1.0, f"Health check took {response_time:.2f} seconds"

        assert response.status_code in [200, 503]

    def test_no_authentication_required(self, client):
        """Test that health endpoint doesn't require authentication."""
        # Health check should work without authentication
        response = client.get('/health')

        # Should not return 401 Unauthorized
        assert response.status_code != 401

        # Should return proper health status
        assert response.status_code in [200, 503]

    def test_cache_headers(self, client):
        """Test cache control headers for health endpoint."""
        response = client.get('/health')

        if 'cache-control' in response.headers:
            cache_control = response.headers['cache-control'].lower()

            # Health checks should not be cached or cached very briefly
            assert 'no-cache' in cache_control or \
                   'no-store' in cache_control or \
                   'max-age=0' in cache_control or \
                   'max-age=1' in cache_control

    def test_concurrent_health_checks(self, client):
        """Test concurrent health check requests."""
        import concurrent.futures

        def check_health():
            return client.get('/health')

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_health) for _ in range(10)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All health checks should succeed
        for response in responses:
            assert response.status_code in [200, 503]

        # All should return consistent status
        statuses = [r.json()['status'] for r in responses]
        # Status should be consistent across concurrent requests
        assert len(set(statuses)) <= 2  # Allow for status change during test

    def test_detailed_health_check(self, client):
        """Test detailed health check with verbose flag."""
        # Some APIs support detailed health checks
        response = client.get('/health?verbose=true')

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            json_response = response.json()

            # Verbose mode might include additional details
            if 'details' in json_response or len(json_response) > 5:
                # Should have more information than basic health check
                assert len(json_response.keys()) >= 4

    def test_service_version_info(self, client):
        """Test that version information is properly formatted."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()
            version = json_response['version']

            # Version should follow some format
            # Could be semantic versioning, date-based, or commit hash
            assert isinstance(version, str)

            # Check for common version patterns
            import re

            # Semantic version (e.g., 1.0.0)
            semantic_pattern = r'^\d+\.\d+\.\d+'
            # Date version (e.g., 2024.01.15)
            date_pattern = r'^\d{4}\.\d{2}\.\d{2}'
            # Commit hash (e.g., abc123)
            hash_pattern = r'^[a-f0-9]{6,}'

            assert (re.match(semantic_pattern, version) or
                    re.match(date_pattern, version) or
                    re.match(hash_pattern, version) or
                    version == 'dev' or
                    version == 'latest'), f"Unexpected version format: {version}"

    def test_database_connectivity(self, client):
        """Test that database connectivity is checked."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()
            services = json_response['services']

            # Database should be one of the checked services
            if 'database' in services or 'db' in services:
                db_status = services.get('database') or services.get('db')
                assert db_status in ['healthy', 'degraded', 'unhealthy', 'up', 'down']

    def test_external_service_checks(self, client):
        """Test that external services (like Huawei OCR) are checked."""
        response = client.get('/health')

        if response.status_code == 200:
            json_response = response.json()
            services = json_response['services']

            # OCR service should be monitored
            ocr_services = ['ocr_service', 'huawei_ocr', 'ocr']
            ocr_status = None

            for service_name in ocr_services:
                if service_name in services:
                    ocr_status = services[service_name]
                    break

            if ocr_status:
                assert ocr_status in ['healthy', 'degraded', 'unhealthy', 'up', 'down']

    def test_readiness_vs_liveness(self, client):
        """Test distinction between readiness and liveness if supported."""
        # Some systems separate readiness (ready to serve) from liveness (not crashed)

        # Liveness check
        liveness_response = client.get('/health/live')
        if liveness_response.status_code != 404:
            assert liveness_response.status_code in [200, 503]

        # Readiness check
        readiness_response = client.get('/health/ready')
        if readiness_response.status_code != 404:
            assert readiness_response.status_code in [200, 503]