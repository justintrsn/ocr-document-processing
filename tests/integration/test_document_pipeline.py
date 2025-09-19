#!/usr/bin/env python
"""
Integration test for complete document processing pipeline
"""

import logging
from pathlib import Path
from typing import Optional, List
import pytest

from src.services.ocr_service import HuaweiOCRService
from src.services.image_quality_service import ImageQualityAssessor
from src.services.llm_enhancement_service import LLMEnhancementService, EnhancementType
from src.services.ocr_confidence_analyzer import OCRConfidenceAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestDocumentPipeline:
    """Test complete document processing pipeline"""

    @pytest.fixture
    def test_document(self):
        """Get test document path"""
        doc_path = Path("tests/documents/scanned_document.jpg")
        assert doc_path.exists(), f"Test document not found: {doc_path}"
        return doc_path

    @pytest.fixture
    def image_quality_service(self):
        """Initialize image quality service"""
        return ImageQualityAssessor()

    @pytest.fixture
    def ocr_service(self):
        """Initialize OCR service"""
        return HuaweiOCRService()

    @pytest.fixture
    def llm_service(self):
        """Initialize LLM enhancement service"""
        return LLMEnhancementService()

    @pytest.fixture
    def confidence_analyzer(self):
        """Initialize OCR confidence analyzer"""
        return OCRConfidenceAnalyzer()

    def test_quality_gate_good_image(self, test_document, image_quality_service):
        """Test quality gate with good quality image"""
        # Assess image quality
        quality_result = image_quality_service.assess(image_path=test_document)

        assert quality_result.overall_score > 30, f"Quality score too low: {quality_result.overall_score}"
        assert quality_result.overall_score <= 100, f"Quality score out of range: {quality_result.overall_score}"

        # Check individual metrics
        assert quality_result.sharpness_score > 0
        assert quality_result.contrast_score > 0
        assert quality_result.resolution_score > 0

        logger.info(f"Image quality: {quality_result.overall_score:.1f}%")
        logger.info(f"Issues detected: {quality_result.issues}")

    def test_ocr_processing(self, test_document, ocr_service):
        """Test OCR processing"""
        # Process document
        ocr_response = ocr_service.process_document(image_path=test_document)

        assert ocr_response is not None
        assert ocr_response.result is not None
        assert len(ocr_response.result) > 0

        # Extract text
        text = ocr_service.extract_text_from_response(ocr_response)
        assert len(text) > 0

        # Check for expected content
        assert "MEDICAL CERTIFICATE" in text.upper()

        logger.info(f"OCR extracted {len(text.split())} words")

    def test_confidence_analysis(self, test_document, ocr_service, confidence_analyzer):
        """Test OCR confidence analysis"""
        # Get OCR results
        ocr_response = ocr_service.process_document(image_path=test_document)

        # Analyze confidence
        confidence_analysis = confidence_analyzer.analyze_confidence(ocr_response)

        assert "summary" in confidence_analysis
        assert "distribution" in confidence_analysis
        assert "problem_areas" in confidence_analysis

        summary = confidence_analysis["summary"]
        assert summary["average_confidence"] > 0
        assert summary["total_words"] > 0

        distribution = confidence_analysis["distribution"]
        assert "high" in distribution
        assert "medium" in distribution
        assert "low" in distribution

        logger.info(f"Confidence distribution: High={distribution['high']['count']}, "
                   f"Medium={distribution['medium']['count']}, Low={distribution['low']['count']}")
        logger.info(f"Problem areas: {len(confidence_analysis['problem_areas'])}")

    def test_llm_enhancement_grammar(self, test_document, ocr_service, llm_service):
        """Test LLM grammar enhancement"""
        # Get OCR results
        ocr_response = ocr_service.process_document(image_path=test_document)

        # Enhance with grammar correction
        result = llm_service.enhance_ocr_result(
            ocr_response,
            enhancement_type=EnhancementType.GRAMMAR,
            document_context="Medical certificate from clinic"
        )

        assert result is not None
        assert result.overall_confidence >= 0
        assert result.summary is not None

        if result.grammar_corrections:
            logger.info(f"Grammar corrections found: {len(result.grammar_corrections)}")
            for correction in result.grammar_corrections[:3]:
                logger.info(f"  '{correction.original}' → '{correction.corrected}'")

    def test_llm_enhancement_selective(self, test_document, ocr_service, llm_service):
        """Test selective LLM enhancement"""
        # Get OCR results
        ocr_response = ocr_service.process_document(image_path=test_document)

        # Test different enhancement types
        enhancement_types = [
            EnhancementType.GRAMMAR,
            EnhancementType.CONTEXT,
            EnhancementType.STRUCTURE
        ]

        for enhancement_type in enhancement_types:
            result = llm_service.enhance_ocr_result(
                ocr_response,
                enhancement_type=enhancement_type,
                document_context="Medical certificate"
            )

            assert result is not None
            logger.info(f"{enhancement_type.value} enhancement: {result.summary}")

    def test_complete_pipeline_with_quality_gate(self,
                                                  test_document,
                                                  image_quality_service,
                                                  ocr_service,
                                                  llm_service,
                                                  confidence_analyzer):
        """Test complete pipeline with quality gate"""

        # Step 1: Quality Gate
        quality_result = image_quality_service.assess(image_path=test_document)
        quality_threshold = 30  # Configurable threshold

        if quality_result.overall_score < quality_threshold:
            logger.warning(f"Image quality {quality_result.overall_score:.1f}% below threshold {quality_threshold}%")
            logger.warning("Skipping OCR and LLM processing")
            return {
                "status": "rejected",
                "reason": "poor_quality",
                "quality_score": quality_result.overall_score
            }

        logger.info(f"✓ Quality gate passed: {quality_result.overall_score:.1f}%")

        # Step 2: OCR Processing
        ocr_response = ocr_service.process_document(image_path=test_document)
        ocr_text = ocr_service.extract_text_from_response(ocr_response)
        logger.info(f"✓ OCR completed: {len(ocr_text.split())} words extracted")

        # Step 3: Confidence Analysis
        confidence_analysis = confidence_analyzer.analyze_confidence(ocr_response)
        ocr_confidence = confidence_analysis["summary"]["average_confidence"]
        logger.info(f"✓ OCR confidence: {ocr_confidence:.2%}")

        # Step 4: Optional LLM Enhancement (configurable)
        enable_enhancements = ["grammar"]  # Can be configured: ["grammar", "context", "structure"] or []

        enhancement_results = {}
        if enable_enhancements:
            for enhancement_type in enable_enhancements:
                if enhancement_type == "grammar":
                    result = llm_service.enhance_ocr_result(
                        ocr_response,
                        enhancement_type=EnhancementType.GRAMMAR,
                        document_context="Medical certificate"
                    )
                    enhancement_results["grammar"] = result
                    logger.info(f"✓ Grammar enhancement: {len(result.grammar_corrections)} corrections")

                # Add other enhancement types as needed

        # Step 5: Calculate Final Confidence
        # Weights: Image(20%), OCR(30%), Grammar(20%), Context(20%), Structure(10%)
        final_confidence = (
            quality_result.overall_score * 0.20 +
            ocr_confidence * 100 * 0.30 +
            (enhancement_results.get("grammar", None).overall_confidence * 100 if "grammar" in enhancement_results else 80) * 0.20 +
            80 * 0.20 +  # Default context score
            80 * 0.10    # Default structure score
        )

        logger.info(f"✓ Final confidence: {final_confidence:.1f}%")

        # Step 6: Routing Decision
        routing_threshold = 80
        if final_confidence >= routing_threshold:
            routing = "automatic"
            logger.info(f"✓ Routing: Automatic processing (confidence >= {routing_threshold}%)")
        else:
            routing = "manual_review"
            logger.info(f"⚠ Routing: Manual review (confidence < {routing_threshold}%)")

        # Return complete pipeline result
        result = {
            "status": "completed",
            "quality_score": quality_result.overall_score,
            "ocr_confidence": ocr_confidence * 100,
            "enhancements_applied": enable_enhancements,
            "final_confidence": final_confidence,
            "routing": routing,
            "text_extracted": len(ocr_text.split()),
            "corrections_made": len(enhancement_results.get("grammar", {}).grammar_corrections) if "grammar" in enhancement_results else 0
        }

        assert result["status"] == "completed"
        assert result["quality_score"] > quality_threshold
        assert result["final_confidence"] > 0

        return result


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])