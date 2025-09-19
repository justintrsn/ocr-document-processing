#!/usr/bin/env python
"""
Test Processing Orchestrator
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
import pytest

from src.services.processing_orchestrator import (
    ProcessingOrchestrator,
    ProcessingConfig,
    ProcessingDecision
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_orchestrator_with_good_document():
    """Test orchestrator with a good quality document"""

    # Configure processing
    config = ProcessingConfig(
        quality_threshold=30.0,
        confidence_threshold=80.0,
        enable_enhancements=["grammar"]  # Only grammar for faster testing
    )

    orchestrator = ProcessingOrchestrator(config)

    # Use test document
    doc_path = Path("tests/documents/scanned_document.jpg")
    if not doc_path.exists():
        logger.warning(f"Test document not found: {doc_path}")
        return

    # Process document
    result = orchestrator.process_document(document_path=doc_path)

    # Verify results
    assert result is not None
    assert result.confidence_report is not None

    # Check that quality gate passed
    assert result.confidence_report.image_quality_score > 30

    # Check OCR was performed
    assert len(result.extracted_text) > 0
    assert "MEDICAL CERTIFICATE" in result.extracted_text.upper()

    # Check enhancement was applied
    if result.enhanced_text:
        logger.info(f"Enhanced text available: {len(result.enhanced_text)} characters")

    # Check routing decision
    assert result.confidence_report.routing_decision in ["automatic", "manual_review"]

    # Check metrics
    assert result.processing_metrics["quality_check_time"] > 0
    assert result.processing_metrics["ocr_processing_time"] > 0
    if "grammar" in result.processing_metrics.get("enhancements_applied", []):
        assert "grammar" in result.processing_metrics["llm_enhancement_time"]

    logger.info(f"Processing completed in {result.processing_metrics['total_processing_time']:.2f}s")
    logger.info(f"Final confidence: {result.confidence_report.final_confidence:.1f}%")
    logger.info(f"Routing: {result.confidence_report.routing_decision}")


def test_orchestrator_quality_gate():
    """Test that quality gate rejects poor quality images"""

    config = ProcessingConfig(
        quality_threshold=90.0,  # Very high threshold
        confidence_threshold=80.0,
        enable_enhancements=[]  # No enhancements
    )

    orchestrator = ProcessingOrchestrator(config)

    # Use test document (will likely fail with 90% threshold)
    doc_path = Path("tests/documents/scanned_document.jpg")
    if not doc_path.exists():
        # Create a low quality test image
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='gray')
        doc_path = Path("tests/test_low_quality.jpg")
        img.save(doc_path, quality=20)

    result = orchestrator.process_document(document_path=doc_path)

    # With 90% threshold, most documents should be rejected or sent to manual review
    assert result is not None

    if result.confidence_report.routing_decision == "rejected":
        logger.info("Document correctly rejected due to low quality")
        assert "quality" in result.error_message.lower()
    else:
        # Document passed quality gate but might still go to manual review
        assert result.confidence_report.final_confidence < 90
        logger.info(f"Document quality: {result.confidence_report.image_quality_score:.1f}%")


def test_orchestrator_no_enhancements():
    """Test orchestrator without LLM enhancements"""

    config = ProcessingConfig(
        quality_threshold=30.0,
        confidence_threshold=80.0,
        enable_enhancements=[]  # No LLM enhancements
    )

    orchestrator = ProcessingOrchestrator(config)

    doc_path = Path("tests/documents/scanned_document.jpg")
    if not doc_path.exists():
        logger.warning("Test document not found")
        return

    result = orchestrator.process_document(document_path=doc_path)

    assert result is not None
    assert len(result.extracted_text) > 0
    assert result.enhanced_text is None or result.enhanced_text == ""
    assert len(result.corrections_made) == 0
    assert result.processing_metrics.get("enhancements_applied", []) == []

    logger.info("Processing without enhancements completed successfully")


def test_orchestrator_cost_estimation():
    """Test cost estimation"""

    orchestrator = ProcessingOrchestrator()

    # Estimate costs
    estimate = orchestrator.estimate_processing_cost(
        document_size_mb=2.0,
        enhancement_types=["grammar", "context"]
    )

    assert "estimated_ocr_cost" in estimate
    assert "estimated_llm_tokens" in estimate
    assert "estimated_total_cost" in estimate
    assert "estimated_total_time" in estimate

    assert estimate["estimated_total_time"] > 0
    assert estimate["estimated_llm_tokens"] > 0

    logger.info(f"Cost estimate: ${estimate['estimated_total_cost']}")
    logger.info(f"Time estimate: {estimate['estimated_total_time']}s")
    logger.info(f"LLM tokens: {estimate['estimated_llm_tokens']}")


if __name__ == "__main__":
    logger.info("Testing Processing Orchestrator...")

    # Run basic test
    test_orchestrator_with_good_document()

    # Test quality gate
    test_orchestrator_quality_gate()

    # Test without enhancements
    test_orchestrator_no_enhancements()

    # Test cost estimation
    test_orchestrator_cost_estimation()

    logger.info("All orchestrator tests completed!")