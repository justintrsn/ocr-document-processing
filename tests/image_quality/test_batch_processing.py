"""
Test batch processing and queue functionality with multiple documents
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.models.quality import QualityAssessment
from tests.config import test_config


class TestBatchProcessing:
    """Test batch processing of multiple documents"""

    def test_assess_all_configured_documents(self, assessor, all_test_documents):
        """Test assessment of all configured documents"""
        if not test_config.is_mode_enabled("batch_processing"):
            pytest.skip("Batch processing disabled in config")

        results = []
        for doc_path in all_test_documents:
            assessment = assessor.assess(image_path=doc_path)
            results.append({
                "document": doc_path.name,
                "assessment": assessment,
                "score": assessment.overall_score
            })

        # Verify we processed at least one document
        assert len(results) > 0

        # Verify all assessments are valid
        for result in results:
            assert isinstance(result["assessment"], QualityAssessment)
            assert 0 <= result["score"] <= 100

        # Print summary for debugging
        print(f"\n📊 Batch Assessment Results:")
        for result in results:
            print(f"  - {result['document']}: {result['score']:.1f} ({result['assessment'].quality_level})")

    def test_parametrized_document_assessment(self, assessor, each_test_document):
        """Test assessment with parametrized fixture (runs once per document)"""
        assessment = assessor.assess(image_path=each_test_document)

        assert isinstance(assessment, QualityAssessment)
        assert assessment.overall_score > 0

        print(f"\n✅ Assessed {each_test_document.name}: {assessment.overall_score:.1f}")

    def test_queue_routing_based_on_confidence(self, assessor, all_test_documents):
        """Test documents are routed to correct queues based on confidence"""
        if not test_config.is_queue_enabled():
            pytest.skip("Queue testing disabled in config")

        ocr_threshold = test_config.get_ocr_threshold()
        queues = {
            "automatic": [],
            "manual_high": [],
            "manual_medium": [],
            "manual_low": []
        }

        for doc_path in all_test_documents:
            assessment = assessor.assess(image_path=doc_path)
            score = assessment.overall_score

            # Route based on confidence score
            if score >= ocr_threshold:
                queues["automatic"].append(doc_path.name)
            elif score < 60:
                queues["manual_high"].append(doc_path.name)
            elif score < 80:
                queues["manual_medium"].append(doc_path.name)
            else:
                queues["manual_low"].append(doc_path.name)

        # Print queue distribution
        print(f"\n📋 Queue Routing (threshold={ocr_threshold}):")
        print(f"  Automatic processing: {queues['automatic']}")
        print(f"  Manual review (high priority): {queues['manual_high']}")
        print(f"  Manual review (medium priority): {queues['manual_medium']}")
        print(f"  Manual review (low priority): {queues['manual_low']}")

        # At least one document should be processed
        total_docs = sum(len(q) for q in queues.values())
        assert total_docs == len(all_test_documents)

    def test_batch_size_limit(self, assessor, all_test_documents):
        """Test batch processing respects configured batch size limit"""
        max_batch_size = test_config.get_max_batch_size()

        # Process in batches
        batches = []
        for i in range(0, len(all_test_documents), max_batch_size):
            batch = all_test_documents[i:i + max_batch_size]
            batches.append(batch)

        print(f"\n📦 Processing {len(all_test_documents)} documents in {len(batches)} batch(es)")

        for batch_idx, batch in enumerate(batches):
            assert len(batch) <= max_batch_size

            batch_results = []
            for doc_path in batch:
                assessment = assessor.assess(image_path=doc_path)
                batch_results.append(assessment)

            print(f"  Batch {batch_idx + 1}: {len(batch)} documents processed")
            assert len(batch_results) == len(batch)

    def test_parallel_assessment_simulation(self, assessor, all_test_document_bytes):
        """Simulate parallel processing of multiple documents"""
        if len(all_test_document_bytes) < 2:
            pytest.skip("Need at least 2 documents for parallel test")

        from concurrent.futures import ThreadPoolExecutor
        import time

        def assess_document(doc_data):
            """Assess a single document"""
            name, doc_bytes = doc_data
            start = time.time()
            assessment = assessor.assess(image_data=doc_bytes)
            elapsed = time.time() - start
            return name, assessment, elapsed

        # Process documents in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(assess_document, doc) for doc in all_test_document_bytes]
            results = [f.result() for f in futures]

        # Print timing results
        print(f"\n⚡ Parallel Processing Results:")
        total_time = sum(r[2] for r in results)
        for name, assessment, elapsed in results:
            print(f"  - {name}: {assessment.overall_score:.1f} (took {elapsed:.2f}s)")
        print(f"  Total processing time: {total_time:.2f}s")

        # Verify all documents processed
        assert len(results) == len(all_test_document_bytes)

    @patch('src.services.image_quality_service.requests.get')
    def test_batch_obs_urls(self, mock_get, assessor, all_obs_test_keys):
        """Test batch processing of OBS URLs"""
        if not test_config.is_mode_enabled("obs_urls"):
            pytest.skip("OBS URL testing disabled")

        from tests.image_quality.fixtures import create_sharp_image

        # Mock responses for all OBS keys
        mock_response = MagicMock()
        mock_response.content = create_sharp_image()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = []
        for obs_key in all_obs_test_keys:
            with patch.object(assessor, '_get_obs_service') as mock_obs:
                mock_obs_service = MagicMock()
                mock_obs_service.get_signed_url.return_value = f'https://obs.example.com/{obs_key}'
                mock_obs.return_value = mock_obs_service

                assessment = assessor.assess(image_url=obs_key)
                results.append((obs_key, assessment))

        # Verify all OBS keys processed
        assert len(results) == len(all_obs_test_keys)

        print(f"\n☁️ OBS Batch Processing Results:")
        for key, assessment in results:
            print(f"  - {key}: {assessment.overall_score:.1f}")

    def test_quality_distribution_analysis(self, assessor, all_test_documents):
        """Analyze quality distribution across all test documents"""
        if len(all_test_documents) < 2:
            pytest.skip("Need multiple documents for distribution analysis")

        scores = []
        quality_counts = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

        for doc_path in all_test_documents:
            assessment = assessor.assess(image_path=doc_path)
            scores.append(assessment.overall_score)
            quality_counts[assessment.quality_level] += 1

        # Calculate statistics
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        print(f"\n📈 Quality Distribution Analysis:")
        print(f"  Documents analyzed: {len(all_test_documents)}")
        print(f"  Average score: {avg_score:.1f}")
        print(f"  Score range: {min_score:.1f} - {max_score:.1f}")
        print(f"  Distribution:")
        for level, count in quality_counts.items():
            percentage = (count / len(all_test_documents)) * 100
            print(f"    - {level}: {count} ({percentage:.0f}%)")

        # Verify statistics
        assert 0 <= avg_score <= 100
        assert min_score <= avg_score <= max_score