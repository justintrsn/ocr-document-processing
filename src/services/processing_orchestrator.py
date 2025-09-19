"""
Document Processing Orchestrator with Quality Gates and Configurable Enhancements
"""

import logging
import time
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from src.models.document import Document, ProcessingStatus
from src.models.api_models import ProcessingResult, ConfidenceReport
from src.models.quality import QualityAssessment
from src.services.image_quality_service import ImageQualityAssessor
from src.services.ocr_service import HuaweiOCRService
from src.services.ocr_confidence_analyzer import OCRConfidenceAnalyzer
from src.services.llm_enhancement_service import LLMEnhancementService

logger = logging.getLogger(__name__)


class ProcessingDecision(str, Enum):
    """Processing routing decisions"""
    AUTOMATIC = "automatic"
    MANUAL_REVIEW = "manual_review"
    REJECTED = "rejected"


@dataclass
class ProcessingConfig:
    """Configuration for document processing"""
    quality_threshold: float = 30.0  # Minimum quality score to proceed
    confidence_threshold: float = 80.0  # Minimum confidence for automatic processing
    enable_enhancements: List[str] = None  # List of enhancements to apply
    max_processing_time: int = 180  # Maximum processing time in seconds (3 minutes)

    # Confidence weights (only Image Quality and OCR used)
    weight_image_quality: float = 0.50
    weight_ocr_confidence: float = 0.50
    weight_grammar_score: float = 0.0  # Disabled
    weight_context_score: float = 0.0   # Disabled
    weight_structure_score: float = 0.0  # Disabled


@dataclass
class ProcessingMetrics:
    """Metrics for processing performance"""
    quality_check_time: float = 0.0
    ocr_processing_time: float = 0.0
    llm_enhancement_time: Dict[str, float] = None
    total_processing_time: float = 0.0
    ocr_tokens_used: int = 0
    llm_tokens_used: int = 0
    estimated_cost: float = 0.0

    def __post_init__(self):
        if self.llm_enhancement_time is None:
            self.llm_enhancement_time = {}


class ProcessingOrchestrator:
    """Orchestrates document processing pipeline with quality gates"""

    def __init__(self, config: Optional[ProcessingConfig] = None):
        """Initialize orchestrator with configuration"""
        self.config = config or ProcessingConfig()

        # Initialize services
        self.image_quality_service = ImageQualityAssessor()
        self.ocr_service = HuaweiOCRService()
        self.confidence_analyzer = OCRConfidenceAnalyzer()
        self.llm_service = LLMEnhancementService()
        self.obs_service = None  # Lazy loaded

        # Metrics tracking
        self.metrics = ProcessingMetrics()

    def process_document(self,
                        document_path: Optional[Path] = None,
                        document_url: Optional[str] = None,
                        document_data: Optional[bytes] = None,
                        config_override: Optional[ProcessingConfig] = None,
                        skip_quality_check: bool = False,
                        skip_ocr: bool = False,
                        skip_enhancement: bool = False) -> ProcessingResult:
        """
        Process document through complete pipeline with quality gates

        Args:
            document_path: Local file path
            document_url: OBS URL or HTTP URL
            document_data: Raw document bytes
            config_override: Optional config to override defaults

        Returns:
            ProcessingResult with complete analysis
        """
        start_time = time.time()
        config = config_override or self.config

        logger.info("Starting document processing pipeline")
        logger.info(f"Config: quality_threshold={config.quality_threshold}, "
                   f"confidence_threshold={config.confidence_threshold}, "
                   f"enhancements={config.enable_enhancements}")

        try:
            # Step 1: Quality Gate (optional)
            quality_result = None
            if not skip_quality_check:
                quality_result = self._perform_quality_check(
                    document_path, document_url, document_data
                )

                if quality_result.overall_score < config.quality_threshold:
                    logger.warning(f"Document rejected: quality {quality_result.overall_score:.1f}% "
                                 f"below threshold {config.quality_threshold}%")
                    return self._create_rejection_result(
                        quality_result,
                        reason=f"Image quality too low: {quality_result.overall_score:.1f}%"
                    )

                logger.info(f"✓ Quality gate passed: {quality_result.overall_score:.1f}%")
            else:
                logger.info("Quality check skipped")
                # Create dummy quality result for compatibility
                from src.models.quality import QualityAssessment
                quality_result = QualityAssessment(
                    sharpness=100.0,
                    contrast=100.0,
                    resolution=100.0,
                    noise_level=0.0,
                    overall_score=100.0,
                    issues=[]
                )

            # Step 2: OCR Processing (optional)
            ocr_result = None
            ocr_text = ""
            confidence_analysis = None
            ocr_confidence = 0.0

            if not skip_ocr:
                ocr_result = self._perform_ocr(document_path, document_url, document_data)

                if not ocr_result:
                    return self._create_error_result(
                        quality_result,
                        error="OCR processing failed"
                    )

                ocr_text = self.ocr_service.extract_text_from_response(ocr_result)
                logger.info(f"✓ OCR completed: {len(ocr_text.split())} words extracted")

                # Step 3: OCR Confidence Analysis
                confidence_analysis = self.confidence_analyzer.analyze_confidence(ocr_result)
                ocr_confidence = confidence_analysis["summary"]["average_confidence"]
                logger.info(f"✓ OCR confidence: {ocr_confidence:.2%}")
            else:
                logger.info("OCR processing skipped")
                # Create minimal confidence analysis
                confidence_analysis = {
                    "summary": {"average_confidence": 1.0, "overall_quality": "skipped"},
                    "problem_areas": []
                }
                ocr_confidence = 1.0

            # Step 4: Optional LLM Enhancement
            enhancement_results = {}
            if config.enable_enhancements and not skip_enhancement and ocr_result:
                enhancement_results = self._perform_enhancements(
                    ocr_result,
                    config.enable_enhancements
                )
            elif skip_enhancement or not ocr_result:
                logger.info("Enhancement skipped")

            # Step 5: Calculate Final Confidence
            final_confidence = self._calculate_final_confidence(
                quality_result,
                ocr_confidence,
                enhancement_results,
                config
            )

            # Step 6: Routing Decision
            routing_decision = self._make_routing_decision(
                final_confidence,
                config.confidence_threshold
            )

            # Calculate total processing time
            self.metrics.total_processing_time = time.time() - start_time

            # Create processing result
            return self._create_processing_result(
                quality_result=quality_result,
                ocr_result=ocr_result,
                ocr_text=ocr_text,
                confidence_analysis=confidence_analysis,
                enhancement_results=enhancement_results,
                final_confidence=final_confidence,
                routing_decision=routing_decision
            )

        except Exception as e:
            logger.error(f"Processing pipeline failed: {e}")
            return self._create_error_result(
                quality_result=None,
                error=str(e)
            )

    def _perform_quality_check(self,
                               document_path: Optional[Path],
                               document_url: Optional[str],
                               document_data: Optional[bytes]) -> QualityAssessment:
        """Perform image quality assessment with timing"""
        start_time = time.time()
        logger.info("Performing image quality check...")

        quality_result = self.image_quality_service.assess(
            image_path=document_path,
            image_url=document_url,
            image_data=document_data
        )

        self.metrics.quality_check_time = time.time() - start_time
        logger.info(f"Quality check completed in {self.metrics.quality_check_time:.2f}s")

        return quality_result

    def _perform_ocr(self,
                     document_path: Optional[Path],
                     document_url: Optional[str],
                     document_data: Optional[bytes]) -> Optional[Any]:
        """Perform OCR processing with timing"""
        start_time = time.time()
        logger.info("Performing OCR processing...")

        try:
            if document_path:
                ocr_result = self.ocr_service.process_document(image_path=document_path)
            elif document_url:
                # Handle OBS URLs by converting to signed URL
                if document_url.startswith('obs://'):
                    # Lazy load OBS service
                    if self.obs_service is None:
                        from src.services.obs_service import OBSService
                        self.obs_service = OBSService()

                    # Parse OBS URL to extract object key
                    parts = document_url[6:].split('/', 1)  # Remove 'obs://' prefix
                    if len(parts) == 2:
                        bucket_name, object_key = parts
                        # Generate signed URL for OCR service
                        signed_url = self.obs_service.get_signed_url(object_key)
                        logger.info(f"Generated signed URL for OCR processing: {object_key}")
                        ocr_result = self.ocr_service.process_document(image_url=signed_url)
                    else:
                        raise ValueError(f"Invalid OBS URL format: {document_url}")
                else:
                    # Regular HTTP/HTTPS URL
                    ocr_result = self.ocr_service.process_document(image_url=document_url)
            elif document_data:
                # Save temporary file for OCR processing
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    tmp_file.write(document_data)
                    tmp_path = Path(tmp_file.name)

                ocr_result = self.ocr_service.process_document(image_path=tmp_path)

                # Clean up temporary file
                tmp_path.unlink()
            else:
                raise ValueError("No document input provided")

            self.metrics.ocr_processing_time = time.time() - start_time
            logger.info(f"OCR completed in {self.metrics.ocr_processing_time:.2f}s")

            return ocr_result

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return None

    def _perform_enhancements(self,
                             ocr_result: Any,
                             enhancement_types: List[str]) -> Dict[str, Any]:
        """Perform LLM enhancement (single call for all types)"""
        enhancement_results = {}

        if not enhancement_types:
            return enhancement_results

        start_time = time.time()
        logger.info(f"Performing LLM enhancement (types: {enhancement_types})...")

        try:
            # Always use COMPLETE mode to get all enhancements in one call
            # This avoids multiple LLM calls and saves time
            result = self.llm_service.enhance_ocr_result(
                ocr_result,
                document_context="Document processing"
            )

            # Store the same result for all requested enhancement types
            # Since COMPLETE mode includes all enhancements
            for enhancement_type in enhancement_types:
                enhancement_results[enhancement_type] = result

            # Track timing (single call time)
            enhancement_time = time.time() - start_time
            self.metrics.llm_enhancement_time["combined"] = enhancement_time
            logger.info(f"✓ LLM enhancement completed in {enhancement_time:.2f}s (single call)")

        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")

        return enhancement_results

    def _calculate_final_confidence(self,
                                   quality_result: Optional[QualityAssessment],
                                   ocr_confidence: float,
                                   enhancement_results: Dict[str, Any],
                                   config: ProcessingConfig) -> float:
        """Calculate weighted final confidence score (only Image Quality and OCR)"""

        # Only use image quality and OCR confidence
        image_score = (quality_result.overall_score / 100.0) if quality_result else 1.0
        ocr_score = ocr_confidence

        # Simple weighted average of just image quality and OCR
        total_weight = config.weight_image_quality + config.weight_ocr_confidence
        weighted_sum = (image_score * config.weight_image_quality +
                       ocr_score * config.weight_ocr_confidence)

        # Calculate final weighted average
        final_confidence = weighted_sum / total_weight if total_weight > 0 else 0

        logger.info(f"Confidence calculation: Image={image_score:.2f}, OCR={ocr_score:.2f} "
                   f"→ Final={final_confidence:.2f}")

        return final_confidence * 100  # Return as percentage

    def _make_routing_decision(self,
                              final_confidence: float,
                              threshold: float) -> ProcessingDecision:
        """Make routing decision based on confidence"""
        if final_confidence >= threshold:
            logger.info(f"✓ Routing: Automatic processing (confidence {final_confidence:.1f}% >= {threshold}%)")
            return ProcessingDecision.AUTOMATIC
        else:
            logger.info(f"⚠ Routing: Manual review (confidence {final_confidence:.1f}% < {threshold}%)")
            return ProcessingDecision.MANUAL_REVIEW

    def _create_processing_result(self,
                                 quality_result: QualityAssessment,
                                 ocr_result: Any,
                                 ocr_text: str,
                                 confidence_analysis: Dict[str, Any],
                                 enhancement_results: Dict[str, Any],
                                 final_confidence: float,
                                 routing_decision: ProcessingDecision) -> ProcessingResult:
        """Create complete processing result"""

        # Get enhanced text if available
        enhanced_text = None
        corrections_made = []

        for enhancement_type, result in enhancement_results.items():
            if result.enhanced_text:
                enhanced_text = result.enhanced_text
            if result.grammar_corrections:
                corrections_made.extend(result.grammar_corrections)

        # Create confidence report
        confidence_report = ConfidenceReport(
            image_quality_score=quality_result.overall_score,
            ocr_confidence_score=confidence_analysis["summary"]["average_confidence"] * 100,
            grammar_score=0,  # Disabled
            context_score=0,  # Disabled
            structure_score=0,  # Disabled
            final_confidence=final_confidence,
            routing_decision=routing_decision.value,
            priority_level="high" if final_confidence < 60 else "medium" if final_confidence < 80 else "low",
            issues_detected=quality_result.issues + [
                f"Low confidence words: {len(confidence_analysis['problem_areas'])}"
            ] if confidence_analysis['problem_areas'] else quality_result.issues
        )

        # Create processing result
        return ProcessingResult(
            document_id="",  # Will be set by API layer
            status=ProcessingStatus.COMPLETED if routing_decision == ProcessingDecision.AUTOMATIC else ProcessingStatus.MANUAL_REVIEW,
            confidence_report=confidence_report,
            extracted_text=ocr_text,
            enhanced_text=enhanced_text,
            corrections_made=[{
                "original": c.original,
                "corrected": c.corrected,
                "confidence": c.confidence,
                "type": c.issue_type
            } for c in corrections_made[:10]],  # Limit to top 10
            processing_metrics={
                "quality_check_time": self.metrics.quality_check_time,
                "ocr_processing_time": self.metrics.ocr_processing_time,
                "llm_enhancement_time": self.metrics.llm_enhancement_time,
                "total_processing_time": self.metrics.total_processing_time,
                "words_extracted": len(ocr_text.split()),
                "corrections_applied": len(corrections_made),
                "enhancements_applied": list(enhancement_results.keys())
            }
        )

    def _create_rejection_result(self,
                                quality_result: Optional[QualityAssessment],
                                reason: str) -> ProcessingResult:
        """Create result for rejected document"""
        confidence_report = ConfidenceReport(
            image_quality_score=quality_result.overall_score if quality_result else 0,
            ocr_confidence_score=0,
            grammar_score=0,  # Disabled
            context_score=0,  # Disabled
            structure_score=0,  # Disabled
            final_confidence=0,
            routing_decision=ProcessingDecision.REJECTED.value,
            priority_level="high",
            issues_detected=[reason]
        )

        return ProcessingResult(
            document_id="",
            status=ProcessingStatus.FAILED,
            confidence_report=confidence_report,
            extracted_text="",
            error_message=reason,
            processing_metrics={
                "quality_check_time": self.metrics.quality_check_time,
                "total_processing_time": time.time()
            }
        )

    def _create_error_result(self,
                           quality_result: Optional[QualityAssessment],
                           error: str) -> ProcessingResult:
        """Create result for processing error"""
        return ProcessingResult(
            document_id="",
            status=ProcessingStatus.FAILED,
            confidence_report=None,
            extracted_text="",
            error_message=error,
            processing_metrics={
                "quality_check_time": self.metrics.quality_check_time,
                "ocr_processing_time": self.metrics.ocr_processing_time,
                "total_processing_time": time.time()
            }
        )

    def estimate_processing_cost(self,
                                document_size_mb: float,
                                enhancement_types: List[str]) -> Dict[str, Any]:
        """
        Estimate processing cost and time

        Args:
            document_size_mb: Document size in MB
            enhancement_types: List of enhancements to apply

        Returns:
            Cost estimation dictionary
        """
        # Estimate based on document size and enhancements
        ocr_cost = document_size_mb * 0.01  # Example: $0.01 per MB

        # Estimate tokens for LLM
        estimated_text_length = document_size_mb * 1000 * 100  # Rough estimate
        llm_tokens = 0

        for enhancement in enhancement_types:
            if enhancement.lower() in ["grammar", "context", "structure"]:
                llm_tokens += int(estimated_text_length / 4)  # ~1 token per 4 chars
            elif enhancement.lower() in ["complete", "all"]:
                llm_tokens += int(estimated_text_length / 2)  # More tokens for complete

        llm_cost = (llm_tokens / 1000) * 0.002  # $0.002 per 1K tokens

        # Time estimates
        quality_time = 0.5
        ocr_time = min(6, document_size_mb * 2)  # Cap at 6 seconds
        llm_time = 25 if enhancement_types else 0  # Single LLM call regardless of types

        return {
            "estimated_ocr_cost": round(ocr_cost, 4),
            "estimated_llm_tokens": llm_tokens,
            "estimated_llm_cost": round(llm_cost, 4),
            "estimated_total_cost": round(ocr_cost + llm_cost, 4),
            "estimated_quality_time": quality_time,
            "estimated_ocr_time": ocr_time,
            "estimated_llm_time": llm_time,
            "estimated_total_time": quality_time + ocr_time + llm_time
        }