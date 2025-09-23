"""
LLM Enhancement Service using DeepSeek V3 for OCR post-processing
Simplified for single COMPLETE call
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.models.ocr_models import OCRResponse
from src.services.ocr_confidence_analyzer import OCRConfidenceAnalyzer

logger = logging.getLogger(__name__)


class GrammarCorrection(BaseModel):
    """Grammar correction suggestion"""
    original: str = Field(description="Original text")
    corrected: str = Field(description="Corrected text")
    confidence: float = Field(description="Confidence in correction (0-1)")
    issue_type: str = Field(description="Type of issue (spelling/grammar/punctuation)")


class EnhancementResult(BaseModel):
    """Complete enhancement result from LLM"""
    enhanced_text: str = Field(description="Fully enhanced/corrected text")
    corrections: List[GrammarCorrection] = Field(default_factory=list, description="List of corrections made")
    overall_confidence: float = Field(description="Overall confidence in enhancements (0-1)")
    summary: str = Field(description="Summary of enhancements made")


@dataclass
class LLMConfig:
    """Configuration for LLM service"""
    model_name: str = None
    api_key: str = None
    base_url: str = None
    temperature: float = 0.1  # Low temperature for consistent results
    timeout: int = 30

    def __post_init__(self):
        """Load from environment if not provided"""
        if not self.api_key:
            self.api_key = os.getenv("MAAS_API_KEY")
            logger.info(f"MAAS_API_KEY loaded from env: {'Yes' if self.api_key else 'No'}")
        if not self.base_url:
            self.base_url = os.getenv("MAAS_BASE_URL", "https://api.modelarts-maas.com/v1")
            logger.info(f"MAAS_BASE_URL: {self.base_url if self.base_url else 'Not set'}")
        if not self.model_name:
            self.model_name = os.getenv("MAAS_MODEL_NAME", "deepseek-v3.1")


class LLMEnhancementService:
    """Service for enhancing OCR results using LLM - Simplified for single call"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM enhancement service"""
        self.config = config or LLMConfig()
        self.llm = self._initialize_llm()
        self.confidence_analyzer = OCRConfidenceAnalyzer()
        self.output_parser = PydanticOutputParser(pydantic_object=EnhancementResult)

    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize LangChain ChatOpenAI for Huawei ModelArts MAAS"""
        if not self.config.api_key or not self.config.base_url:
            logger.error(f"MAAS configuration missing - API_KEY: {bool(self.config.api_key)}, BASE_URL: {bool(self.config.base_url)}")
            logger.error(f"Environment check - MAAS_API_KEY: {bool(os.getenv('MAAS_API_KEY'))}, MAAS_BASE_URL: {bool(os.getenv('MAAS_BASE_URL'))}")
            raise ValueError("MAAS_API_KEY and MAAS_BASE_URL must be set in environment or config")

        return ChatOpenAI(
            model=self.config.model_name,
            openai_api_key=self.config.api_key,
            openai_api_base=self.config.base_url,
            temperature=self.config.temperature,
            timeout=self.config.timeout
        )

    def enhance_ocr_result(self,
                          ocr_response: OCRResponse,
                          document_context: Optional[str] = None) -> EnhancementResult:
        """
        Enhance OCR results using single LLM call (COMPLETE mode)

        Args:
            ocr_response: OCR response from Huawei service
            document_context: Optional additional context about the document

        Returns:
            Enhancement result with corrections and enhanced text
        """
        # Extract text and analyze confidence
        ocr_text = self._extract_text_from_ocr(ocr_response)
        confidence_analysis = self.confidence_analyzer.analyze_confidence(ocr_response)

        # Build comprehensive enhancement prompt
        prompt = self._build_enhancement_prompt(
            ocr_text,
            confidence_analysis,
            document_context
        )

        try:
            # Single LLM call for complete enhancement
            logger.info("Performing comprehensive OCR enhancement (single LLM call)")
            logger.debug(f"OCR text length: {len(ocr_text)} characters")

            # Create prompt template with format instructions
            format_instructions = self.output_parser.get_format_instructions()

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are an expert document analyst specializing in OCR post-processing and enhancement."),
                ("human", prompt + "\n\nOutput Format:\n{format_instructions}")
            ])

            # Format the prompt and call LLM
            formatted_prompt = prompt_template.format_messages(
                format_instructions=format_instructions
            )

            response = self.llm.invoke(formatted_prompt)

            # Parse the structured response
            result = self.output_parser.parse(response.content)
            logger.info("LLM enhancement completed successfully")

            return result

        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")
            # Return fallback result with original text
            return EnhancementResult(
                enhanced_text=ocr_text,
                corrections=[],
                overall_confidence=0.0,
                summary="Enhancement failed - returning original text"
            )

    def _build_enhancement_prompt(self,
                                 ocr_text: str,
                                 confidence_analysis: Dict[str, Any],
                                 document_context: Optional[str] = None) -> str:
        """Build comprehensive enhancement prompt for single LLM call"""

        prompt = f"""
        COMPREHENSIVE OCR ENHANCEMENT TASK

        OCR EXTRACTED TEXT:
        {ocr_text}

        OCR CONFIDENCE ANALYSIS:
        - Average confidence: {confidence_analysis.get('average_confidence', 0):.2%}
        - High confidence words: {confidence_analysis.get('confidence_distribution', {}).get('high', 0)}
        - Medium confidence words: {confidence_analysis.get('confidence_distribution', {}).get('medium', 0)}
        - Low confidence words: {confidence_analysis.get('confidence_distribution', {}).get('low', 0)}
        """

        # Add problem areas if any
        problem_areas = confidence_analysis.get('problem_areas', [])
        if problem_areas:
            prompt += "\n\nLOW CONFIDENCE AREAS TO FOCUS ON:"
            for area in problem_areas[:5]:  # Limit to top 5 problem areas
                prompt += f"\n- '{area['text']}' (confidence: {area['confidence']:.2%})"

        # Add document context if provided
        if document_context:
            prompt += f"\n\nDOCUMENT CONTEXT:\n{document_context}"

        prompt += """

        YOUR TASKS (Single comprehensive analysis):
        1. CORRECT ERRORS: Fix spelling, grammar, and punctuation errors
        2. IMPROVE CLARITY: Enhance readability while preserving meaning
        3. FOCUS ON LOW-CONFIDENCE AREAS: Pay special attention to text marked with low confidence
        4. PRESERVE CRITICAL INFORMATION: Keep document IDs, numbers, and proper names intact
        5. PROVIDE ENHANCED VERSION: Return a fully corrected version of the text

        IMPORTANT GUIDELINES:
        - Maintain high accuracy - only make corrections you're confident about
        - Preserve original formatting where important (document structure, line breaks for addresses, etc.)
        - For Chinese text, ensure proper character recognition and grammar
        - For English text, ensure proper spelling and grammar
        - If unsure about a correction, keep the original text
        - List all corrections made with confidence scores

        Return a structured response with:
        - enhanced_text: The fully corrected and enhanced text
        - corrections: List of specific corrections made
        - overall_confidence: Your confidence in the enhancement (0-1)
        - summary: Brief summary of improvements made
        """

        return prompt

    def _extract_text_from_ocr(self, ocr_response: OCRResponse) -> str:
        """Extract text from OCR response"""
        texts = []

        if ocr_response.result:
            for result in ocr_response.result:
                if result.ocr_result and result.ocr_result.words_block_list:
                    for word_block in result.ocr_result.words_block_list:
                        texts.append(word_block.words)

        return " ".join(texts)

    def enhance_with_options(self,
                            ocr_response: OCRResponse,
                            enhancement_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Wrapper method for backward compatibility with orchestrator
        Always performs single COMPLETE enhancement regardless of enhancement_types

        Args:
            ocr_response: OCR response
            enhancement_types: Ignored - always performs complete enhancement

        Returns:
            Dictionary with enhancement results
        """
        result = self.enhance_ocr_result(ocr_response)

        return {
            "complete": result,
            "enhanced_text": result.enhanced_text,
            "corrections": [
                {
                    "original": c.original,
                    "corrected": c.corrected,
                    "confidence": c.confidence,
                    "type": c.issue_type
                }
                for c in result.corrections
            ],
            "confidence": result.overall_confidence,
            "summary": result.summary
        }