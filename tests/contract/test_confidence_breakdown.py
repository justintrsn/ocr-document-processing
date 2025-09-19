"""Contract tests for GET /documents/{id}/confidence endpoint."""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.api.main import app  # Will be created later


class TestConfidenceBreakdownContract:
    """Contract tests for confidence breakdown endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def processed_document_id(self):
        """Mock ID for a processed document."""
        return str(uuid.uuid4())

    def test_detailed_confidence_scores(self, client, processed_document_id):
        """Test detailed confidence score breakdown."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()

            # Verify required fields
            required_fields = [
                'document_id', 'overall_confidence', 'confidence_level',
                'components', 'routing_decision', 'routing_reason',
                'threshold', 'meets_threshold', 'risk_level', 'risk_factors'
            ]

            for field in required_fields:
                assert field in json_response, f"Missing required field: {field}"

            # Verify overall confidence
            assert isinstance(json_response['overall_confidence'], (int, float))
            assert 0 <= json_response['overall_confidence'] <= 100

            # Verify confidence level
            assert json_response['confidence_level'] in ['high', 'medium', 'low']

            # Verify threshold
            assert isinstance(json_response['threshold'], (int, float))
            assert json_response['threshold'] == 80  # As per spec

    def test_component_scores_structure(self, client, processed_document_id):
        """Test individual component scores structure."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()
            components = json_response['components']

            assert isinstance(components, list)
            assert len(components) > 0

            # Expected components based on spec
            expected_components = [
                'Image Quality',
                'OCR Confidence',
                'Grammar Score',
                'Context Score',
                'Structure Score'
            ]

            component_names = [c.get('name') for c in components]
            for expected in expected_components:
                assert expected in component_names, f"Missing component: {expected}"

            # Verify each component structure
            for component in components:
                assert 'name' in component
                assert 'score' in component
                assert 'weight' in component
                assert 'weighted_score' in component

                # Verify score range
                assert 0 <= component['score'] <= 100
                # Verify weight range
                assert 0 <= component['weight'] <= 1
                # Verify weighted score calculation
                expected_weighted = component['score'] * component['weight']
                assert abs(component['weighted_score'] - expected_weighted) < 0.01

    def test_weight_calculations(self, client, processed_document_id):
        """Test that component weights sum to 1.0."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()
            components = json_response['components']

            # Sum all weights
            total_weight = sum(c['weight'] for c in components)

            # Should sum to 1.0 (allowing small floating point error)
            assert abs(total_weight - 1.0) < 0.001, f"Weights sum to {total_weight}, expected 1.0"

            # Verify specific weights from spec
            weight_map = {c['name']: c['weight'] for c in components}

            expected_weights = {
                'Image Quality': 0.2,
                'OCR Confidence': 0.3,
                'Grammar Score': 0.2,
                'Context Score': 0.2,
                'Structure Score': 0.1
            }

            for name, expected_weight in expected_weights.items():
                if name in weight_map:
                    assert abs(weight_map[name] - expected_weight) < 0.001

    def test_threshold_comparison(self, client, processed_document_id):
        """Test threshold comparison logic."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()
            overall_confidence = json_response['overall_confidence']
            threshold = json_response['threshold']
            meets_threshold = json_response['meets_threshold']

            # Verify meets_threshold is correct
            expected_meets = overall_confidence >= threshold
            assert meets_threshold == expected_meets

            # Verify routing decision aligns with threshold
            routing = json_response['routing_decision']
            if meets_threshold:
                # Could be automatic or manual based on other factors
                assert routing in ['automatic', 'manual_review']
            else:
                # Below threshold should typically be manual
                assert routing == 'manual_review'

    def test_risk_assessment(self, client, processed_document_id):
        """Test risk level assessment."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()

            # Verify risk level
            risk_level = json_response['risk_level']
            assert risk_level in ['low', 'medium', 'high']

            # Verify risk factors
            risk_factors = json_response['risk_factors']
            assert isinstance(risk_factors, list)

            # Risk level should correlate with confidence
            overall_confidence = json_response['overall_confidence']
            if overall_confidence < 30:
                assert risk_level in ['high', 'medium']
            elif overall_confidence > 80:
                assert risk_level in ['low', 'medium']

    def test_review_reasons(self, client, processed_document_id):
        """Test review reasons for manual review cases."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()

            if 'review_reasons' in json_response:
                review_reasons = json_response['review_reasons']
                assert isinstance(review_reasons, list)

                # If routing is manual_review, should have reasons
                if json_response['routing_decision'] == 'manual_review':
                    assert len(review_reasons) > 0

                # Check reason format
                for reason in review_reasons:
                    assert isinstance(reason, str)
                    assert len(reason) > 0

    def test_non_existent_document(self, client):
        """Test confidence request for non-existent document."""
        non_existent_id = str(uuid.uuid4())
        response = client.get(f'/documents/{non_existent_id}/confidence')

        assert response.status_code == 404
        assert 'error' in response.json()

    def test_unprocessed_document(self, client):
        """Test confidence for document not yet processed."""
        unprocessed_id = str(uuid.uuid4())
        response = client.get(f'/documents/{unprocessed_id}/confidence')

        # Should return 409 or 404
        assert response.status_code in [404, 409]

        if response.status_code == 409:
            json_response = response.json()
            assert 'error' in json_response
            assert 'process' in json_response['message'].lower()

    def test_confidence_level_boundaries(self, client, processed_document_id):
        """Test confidence level categorization."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()
            confidence = json_response['overall_confidence']
            level = json_response['confidence_level']

            # Verify level matches confidence score
            if confidence >= 85:
                assert level == 'high'
            elif confidence >= 60:
                assert level == 'medium'
            else:
                assert level == 'low'

    def test_routing_reason_clarity(self, client, processed_document_id):
        """Test that routing reason is clear and informative."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 200:
            json_response = response.json()
            routing_reason = json_response['routing_reason']

            assert isinstance(routing_reason, str)
            assert len(routing_reason) > 10  # Should be descriptive

            # Should mention confidence or threshold
            assert any(word in routing_reason.lower() 
                      for word in ['confidence', 'threshold', 'quality', 'issue'])

    def test_authentication_required(self, client, processed_document_id):
        """Test authentication for confidence endpoint."""
        response = client.get(f'/documents/{processed_document_id}/confidence')

        if response.status_code == 401:
            # Test with API key
            headers = {'X-API-Key': 'test-api-key'}
            response = client.get(
                f'/documents/{processed_document_id}/confidence',
                headers=headers
            )
            assert response.status_code in [200, 401, 404]