"""
Response Builder Service for OCR API
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.models.ocr_api import (
    OCRResponseFull,
    OCRResponseMinimal,
    OCRResponseOCROnly,
    QualityCheckResponse,
    OCRResultResponse,
    EnhancementResponse,
    ConfidenceReportResponse,
    MetadataResponse,
    ThresholdSettings,
    OCRRequest
)
from src.models.api_models import ProcessingResult

logger = logging.getLogger(__name__)


class ResponseBuilder:
    """Service to build different response formats from processing results"""

    def build_full(self,
                   document_id: str,
                   result: ProcessingResult,
                   request: OCRRequest,
                   processing_time_ms: float) -> OCRResponseFull:
        """
        Build full response with all details

        Args:
            document_id: Document identifier
            result: Processing result from orchestrator
            request: Original OCR request
            processing_time_ms: Total processing time

        Returns:
            Complete OCR response
        """
        # Build quality check response if performed
        quality_check = None
        if request.processing_options.enable_quality_check and result.confidence_report:
            quality_check = QualityCheckResponse(
                performed=True,
                passed=result.confidence_report.image_quality_score >= request.thresholds.image_quality_threshold,
                score=result.confidence_report.image_quality_score,
                metrics=self._extract_quality_metrics(result),
                issues=result.confidence_report.issues_detected or [],
                processing_time_ms=result.processing_metrics.get("quality_check_time", 0) * 1000 if result.processing_metrics else None
            )

        # Build OCR result response if performed
        ocr_result = None
        if request.processing_options.enable_ocr and result.extracted_text:
            ocr_result = OCRResultResponse(
                raw_text=result.extracted_text,
                word_count=len(result.extracted_text.split()),
                confidence_score=result.confidence_report.ocr_confidence_score if result.confidence_report else 0,
                confidence_distribution=self._extract_confidence_distribution(result),
                raw_response=self._extract_raw_ocr(result),
                processing_time_ms=result.processing_metrics.get("ocr_processing_time", 0) * 1000 if result.processing_metrics else None
            )

        # Build enhancement response if performed
        enhancement = None
        if request.processing_options.enable_enhancement:
            enhancement = EnhancementResponse(
                performed=bool(result.enhanced_text),
                enhanced_text=result.enhanced_text,
                corrections=result.corrections_made or [],
                processing_time_ms=self._get_enhancement_time(result),
                tokens_used=None  # Could extract from metrics if available
            )

        # Build confidence report
        confidence_report = ConfidenceReportResponse(
            image_quality_score=result.confidence_report.image_quality_score if result.confidence_report else 0,
            ocr_confidence_score=result.confidence_report.ocr_confidence_score if result.confidence_report else 0,
            final_confidence=result.confidence_report.final_confidence if result.confidence_report else 0,
            thresholds_applied=request.thresholds,
            routing_decision=self._determine_routing(result, request.thresholds),
            routing_reason=self._get_routing_reason(result, request.thresholds),
            quality_check_passed=self._check_quality_passed(result, request.thresholds),
            confidence_check_passed=self._check_confidence_passed(result, request.thresholds)
        )

        # Build metadata
        metadata = MetadataResponse(
            document_id=document_id,
            timestamp=datetime.now(),
            processing_time_ms=processing_time_ms
        )

        return OCRResponseFull(
            status="success",
            quality_check=quality_check,
            ocr_result=ocr_result,
            enhancement=enhancement,
            confidence_report=confidence_report,
            metadata=metadata
        )

    def build_minimal(self,
                     document_id: str,
                     result: ProcessingResult,
                     processing_time_ms: float) -> OCRResponseMinimal:
        """
        Build minimal response with essential data only

        Args:
            document_id: Document identifier
            result: Processing result
            processing_time_ms: Total processing time

        Returns:
            Minimal OCR response
        """
        # Get final text (enhanced if available, otherwise raw)
        extracted_text = result.enhanced_text if result.enhanced_text else result.extracted_text

        return OCRResponseMinimal(
            status="success",
            extracted_text=extracted_text or "",
            routing_decision="pass" if result.confidence_report and result.confidence_report.routing_decision == "automatic" else "requires_review",
            confidence_score=result.confidence_report.final_confidence if result.confidence_report else 0,
            document_id=document_id
        )

    def build_ocr_only(self,
                      document_id: str,
                      result: ProcessingResult,
                      processing_time_ms: float) -> OCRResponseOCROnly:
        """
        Build OCR-only response

        Args:
            document_id: Document identifier
            result: Processing result
            processing_time_ms: Total processing time

        Returns:
            OCR-only response
        """
        return OCRResponseOCROnly(
            status="success",
            raw_text=result.extracted_text or "",
            word_count=len(result.extracted_text.split()) if result.extracted_text else 0,
            ocr_confidence=result.confidence_report.ocr_confidence_score if result.confidence_report else 0,
            processing_time_ms=processing_time_ms,
            document_id=document_id
        )

    def _extract_quality_metrics(self, result: ProcessingResult) -> Dict[str, float]:
        """Extract quality metrics from processing result"""
        # This would need to be stored in ProcessingResult
        # For now, return defaults
        return {
            "sharpness": 85.0,
            "contrast": 80.0,
            "resolution": 82.0,
            "noise_level": 5.0
        }

    def _extract_confidence_distribution(self, result: ProcessingResult) -> Dict[str, int]:
        """Extract confidence distribution from result"""
        # This would need to be extracted from the confidence analysis
        # For now, return example distribution
        return {
            "high": 120,
            "medium": 25,
            "low": 5,
            "very_low": 0
        }

    def _extract_raw_ocr(self, result: ProcessingResult) -> Optional[Dict[str, Any]]:
        """Extract raw OCR response if available"""
        # This would need to be stored in ProcessingResult
        # For now, return None (can be extended)
        return None

    def _get_enhancement_time(self, result: ProcessingResult) -> Optional[float]:
        """Get enhancement processing time in milliseconds"""
        if result.processing_metrics and "llm_enhancement_time" in result.processing_metrics:
            times = result.processing_metrics["llm_enhancement_time"]
            if isinstance(times, dict):
                # Sum all enhancement times
                total = sum(times.values())
                return total * 1000  # Convert to ms
            elif isinstance(times, (int, float)):
                return times * 1000
        return None

    def _determine_routing(self, result: ProcessingResult, thresholds: ThresholdSettings) -> str:
        """Determine routing decision based on thresholds"""
        if not result.confidence_report:
            return "requires_review"

        quality_passed = result.confidence_report.image_quality_score >= thresholds.image_quality_threshold
        confidence_passed = result.confidence_report.final_confidence >= thresholds.confidence_threshold

        return "pass" if (quality_passed and confidence_passed) else "requires_review"

    def _get_routing_reason(self, result: ProcessingResult, thresholds: ThresholdSettings) -> str:
        """Get routing decision reason"""
        if not result.confidence_report:
            return "No confidence report available"

        quality_passed = result.confidence_report.image_quality_score >= thresholds.image_quality_threshold
        confidence_passed = result.confidence_report.final_confidence >= thresholds.confidence_threshold

        if quality_passed and confidence_passed:
            return "All thresholds met"
        elif not quality_passed and not confidence_passed:
            return "Both image quality and confidence below thresholds"
        elif not quality_passed:
            return f"Image quality ({result.confidence_report.image_quality_score:.1f}%) below threshold ({thresholds.image_quality_threshold}%)"
        else:
            return f"Confidence ({result.confidence_report.final_confidence:.1f}%) below threshold ({thresholds.confidence_threshold}%)"

    def _check_quality_passed(self, result: ProcessingResult, thresholds: ThresholdSettings) -> bool:
        """Check if quality threshold passed"""
        if not result.confidence_report:
            return False
        return result.confidence_report.image_quality_score >= thresholds.image_quality_threshold

    def _check_confidence_passed(self, result: ProcessingResult, thresholds: ThresholdSettings) -> bool:
        """Check if confidence threshold passed"""
        if not result.confidence_report:
            return False
        return result.confidence_report.final_confidence >= thresholds.confidence_threshold