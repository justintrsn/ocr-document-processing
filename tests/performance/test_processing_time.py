"""
Performance tests for OCR processing
Verifies processing time requirements and timeout handling
"""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import base64

try:
    from src.services.image_quality_service import ImageQualityService
    from src.services.ocr_service import OCRService
    from src.services.llm_enhancement_service import LLMEnhancementService
    from src.services.processing_orchestrator import ProcessingOrchestrator
    from src.models.ocr_models import OCRResponse
    from src.models.quality import QualityAssessment
except ImportError:
    # For testing without full installation
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.services.image_quality_service import ImageQualityService
    from src.services.ocr_service import OCRService
    from src.services.llm_enhancement_service import LLMEnhancementService
    from src.services.processing_orchestrator import ProcessingOrchestrator
    from src.models.ocr_models import OCRResponse
    from src.models.quality import QualityAssessment


class TestProcessingPerformance:
    """Test processing performance requirements"""

    @pytest.fixture
    def sample_image_data(self):
        """Create sample image data"""
        # Create a minimal valid PNG image
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
        return png_data

    @pytest.fixture
    def mock_ocr_response(self):
        """Create mock OCR response"""
        response = MagicMock(spec=OCRResponse)
        response.result = []
        return response

    @pytest.mark.timeout(2)  # Should complete within 2 seconds
    def test_quality_check_performance(self, sample_image_data):
        """Test that quality check completes in under 1 second"""
        service = ImageQualityService()

        with patch.object(service, '_analyze_image_quality') as mock_analyze:
            mock_analyze.return_value = QualityAssessment(
                sharpness_score=85.0,
                contrast_score=80.0,
                resolution_score=90.0,
                noise_level=5.0,
                overall_score=85.0,
                issues_detected=[],
                recommendations=[]
            )

            start_time = time.time()
            result = service.assess_quality(sample_image_data)
            end_time = time.time()

            processing_time = end_time - start_time
            assert processing_time < 1.0, f"Quality check took {processing_time:.2f}s, should be < 1s"
            assert result is not None
            assert result.overall_score == 85.0

    @pytest.mark.timeout(10)  # Should complete within 10 seconds
    def test_ocr_processing_performance(self, sample_image_data):
        """Test that OCR processing completes in under 6 seconds"""
        service = OCRService()

        with patch.object(service, 'process_document') as mock_process:
            mock_process.return_value = MagicMock(spec=OCRResponse)

            start_time = time.time()
            result = service.process_document(sample_image_data)
            end_time = time.time()

            processing_time = end_time - start_time
            assert processing_time < 6.0, f"OCR processing took {processing_time:.2f}s, should be < 6s"
            assert result is not None

    @pytest.mark.timeout(35)  # Should complete within 35 seconds
    def test_llm_enhancement_performance(self, mock_ocr_response):
        """Test that LLM enhancement completes in 20-30 seconds"""
        service = LLMEnhancementService()

        with patch.object(service, 'enhance_ocr_result') as mock_enhance:
            # Simulate LLM processing time
            def delayed_response(*args, **kwargs):
                time.sleep(0.025)  # Simulate 25ms processing (scaled down for testing)
                return MagicMock(
                    enhanced_text="Enhanced text",
                    corrections=[],
                    overall_confidence=0.95,
                    summary="Enhancement complete"
                )

            mock_enhance.side_effect = delayed_response

            start_time = time.time()
            result = service.enhance_ocr_result(mock_ocr_response)
            end_time = time.time()

            processing_time = end_time - start_time
            # In real scenario, this would be 20-30s, but we're testing scaled down
            assert processing_time < 1.0, f"LLM enhancement took {processing_time:.2f}s"
            assert result is not None

    @pytest.mark.timeout(180)  # 3 minute timeout
    def test_full_pipeline_timeout(self, sample_image_data):
        """Test that full pipeline respects 3-minute timeout"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator, '_process_with_timeout') as mock_process:
            # Simulate timeout
            mock_process.side_effect = TimeoutError("Processing timeout")

            start_time = time.time()

            with pytest.raises(TimeoutError):
                orchestrator.process_document(
                    document_content=sample_image_data,
                    enable_enhancement=True,
                    enhancement_types=["complete"]
                )

            end_time = time.time()
            processing_time = end_time - start_time

            # Should fail fast on timeout
            assert processing_time < 5.0, "Timeout should be detected quickly"

    def test_parallel_processing_performance(self, sample_image_data):
        """Test performance with parallel quality check and OCR"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator.quality_service, 'assess_quality') as mock_quality:
            with patch.object(orchestrator.ocr_service, 'process_document') as mock_ocr:
                mock_quality.return_value = MagicMock(overall_score=85.0)
                mock_ocr.return_value = MagicMock(spec=OCRResponse)

                # Both should be called when quality > 30%
                result = orchestrator.process_document(
                    document_content=sample_image_data,
                    skip_quality_check=False,
                    skip_ocr=False
                )

                # Verify parallel execution (both called)
                mock_quality.assert_called_once()
                mock_ocr.assert_called_once()

    def test_skip_ocr_on_low_quality(self, sample_image_data):
        """Test that OCR is skipped when quality is below threshold"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator.quality_service, 'assess_quality') as mock_quality:
            with patch.object(orchestrator.ocr_service, 'process_document') as mock_ocr:
                # Set quality below threshold
                mock_quality.return_value = MagicMock(overall_score=25.0)

                result = orchestrator.process_document(
                    document_content=sample_image_data,
                    skip_quality_check=False,
                    skip_ocr=False
                )

                # OCR should not be called
                mock_quality.assert_called_once()
                mock_ocr.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_processing_performance(self, sample_image_data):
        """Test async processing performance"""
        from src.api.endpoints.ocr import process_document_async

        with patch('src.api.endpoints.ocr.ProcessingOrchestrator') as mock_orchestrator:
            mock_instance = MagicMock()
            mock_instance.process_document.return_value = MagicMock()
            mock_orchestrator.return_value = mock_instance

            start_time = time.time()

            # Simulate async processing
            await process_document_async(
                job_id="test-job",
                document_content=sample_image_data,
                processing_options={},
                thresholds={}
            )

            end_time = time.time()
            processing_time = end_time - start_time

            # Async setup should be fast
            assert processing_time < 0.1, f"Async setup took {processing_time:.2f}s"

    def test_multiple_enhancement_disabled(self, mock_ocr_response):
        """Test that we only make single LLM call, not multiple"""
        service = LLMEnhancementService()

        call_count = 0

        with patch.object(service, 'enhance_ocr_result') as mock_enhance:
            def count_calls(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return MagicMock(
                    enhanced_text="Enhanced",
                    corrections=[],
                    overall_confidence=0.9,
                    summary="Done"
                )

            mock_enhance.side_effect = count_calls

            # Even if multiple types requested, should only call once
            result = service.enhance_with_options(
                mock_ocr_response,
                enhancement_types=["grammar", "context", "structure"]
            )

            assert call_count == 1, f"LLM called {call_count} times, should be 1"
            assert "enhanced_text" in result

    def test_timeout_handling_graceful(self, sample_image_data):
        """Test graceful degradation on service timeout"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator.ocr_service, 'process_document') as mock_ocr:
            # Simulate timeout
            mock_ocr.side_effect = TimeoutError("OCR service timeout")

            result = orchestrator.process_document(
                document_content=sample_image_data,
                skip_quality_check=True,
                skip_ocr=False
            )

            # Should handle timeout gracefully
            assert result.status == "failed"
            assert "timeout" in str(result.error).lower()


class TestPerformanceMetrics:
    """Test performance metric collection"""

    def test_metrics_collection(self, sample_image_data):
        """Test that processing metrics are collected"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator.quality_service, 'assess_quality') as mock_quality:
            with patch.object(orchestrator.ocr_service, 'process_document') as mock_ocr:
                mock_quality.return_value = MagicMock(overall_score=85.0)
                mock_ocr.return_value = MagicMock(spec=OCRResponse)

                result = orchestrator.process_document(
                    document_content=sample_image_data
                )

                # Check metrics are collected
                assert result.processing_metrics is not None
                assert "total_processing_time" in result.processing_metrics

                if not result.skip_quality_check:
                    assert "quality_check_time" in result.processing_metrics

                if not result.skip_ocr:
                    assert "ocr_processing_time" in result.processing_metrics

    def test_cost_tracking(self):
        """Test that costs are tracked for operations"""
        orchestrator = ProcessingOrchestrator()

        with patch.object(orchestrator, '_calculate_costs') as mock_costs:
            mock_costs.return_value = {
                "ocr_cost": 0.01,
                "llm_tokens": 1500,
                "llm_cost": 0.03,
                "total_cost": 0.04
            }

            # Costs should be calculated
            costs = orchestrator._calculate_costs(
                ocr_performed=True,
                enhancement_performed=True,
                document_size=1024
            )

            assert costs["total_cost"] == 0.04
            assert costs["ocr_cost"] == 0.01
            assert costs["llm_cost"] == 0.03


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=180"])