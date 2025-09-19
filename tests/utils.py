"""
Test utility functions for OCR processing tests
"""

import base64
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock
import hashlib
import random
import string


def create_test_image(width: int = 100, height: int = 100) -> bytes:
    """
    Create a test image with specified dimensions

    Args:
        width: Image width
        height: Image height

    Returns:
        PNG image bytes
    """
    # For simplicity, return a minimal PNG
    # In real tests, could use PIL to create proper test images
    png_header = b'\x89PNG\r\n\x1a\n'
    ihdr = b'\x00\x00\x00\rIHDR'
    ihdr += width.to_bytes(4, 'big')
    ihdr += height.to_bytes(4, 'big')
    ihdr += b'\x08\x06\x00\x00\x00'  # bit depth, color type, etc.

    # Calculate CRC (simplified)
    crc = b'\x1f\x15\xc4\x89'

    # Minimal IDAT chunk
    idat = b'\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00'

    # IEND chunk
    iend = b'\x00\x00\x00\x00IEND\xaeB`\x82'

    return png_header + ihdr + crc + idat + iend


def encode_image_base64(image_data: bytes) -> str:
    """Encode image data to base64 string"""
    return base64.b64encode(image_data).decode('utf-8')


def decode_base64_image(base64_str: str) -> bytes:
    """Decode base64 string to image bytes"""
    return base64.b64decode(base64_str)


def create_mock_ocr_words(text: str, base_confidence: float = 0.9) -> List[Dict[str, Any]]:
    """
    Create mock OCR word blocks from text

    Args:
        text: Text to convert to word blocks
        base_confidence: Base confidence score

    Returns:
        List of word block dictionaries
    """
    words = text.split()
    word_blocks = []
    x = 0

    for word in words:
        # Add some variance to confidence
        confidence = base_confidence + random.uniform(-0.1, 0.1)
        confidence = max(0.0, min(1.0, confidence))

        word_block = {
            "words": word,
            "confidence": confidence,
            "location": [[x, 0], [x + len(word) * 10, 0],
                        [x + len(word) * 10, 20], [x, 20]]
        }
        word_blocks.append(word_block)
        x += len(word) * 10 + 10

    return word_blocks


def create_mock_ocr_response(text: str, confidence: float = 0.9) -> Dict[str, Any]:
    """
    Create a complete mock OCR response

    Args:
        text: Text content
        confidence: Average confidence

    Returns:
        Mock OCR response dictionary
    """
    return {
        "result": [{
            "ocr_result": {
                "words_block_list": create_mock_ocr_words(text, confidence),
                "direction": 0.0
            },
            "table_result": {"table_list": []},
            "formula_result": {"formula_list": []},
            "kv_result": {"kv_block_list": []},
            "layout_result": {"layout_block_list": []}
        }]
    }


def create_mock_quality_assessment(score: float = 85.0) -> Dict[str, Any]:
    """
    Create mock quality assessment result

    Args:
        score: Overall quality score

    Returns:
        Quality assessment dictionary
    """
    issues = []
    recommendations = []

    if score < 30:
        issues = ["Very low image quality", "Blurry", "Poor contrast"]
        recommendations = ["Rescan document", "Improve lighting", "Use higher resolution"]
    elif score < 60:
        issues = ["Low sharpness", "Some noise"]
        recommendations = ["Consider rescanning", "Clean document surface"]

    return {
        "sharpness_score": score + random.uniform(-5, 5),
        "contrast_score": score + random.uniform(-5, 5),
        "resolution_score": score + random.uniform(-5, 5),
        "noise_level": max(0, 100 - score + random.uniform(-10, 10)),
        "overall_score": score,
        "issues_detected": issues,
        "recommendations": recommendations
    }


def create_mock_enhancement(original_text: str, corrections: int = 2) -> Dict[str, Any]:
    """
    Create mock LLM enhancement result

    Args:
        original_text: Original OCR text
        corrections: Number of corrections to simulate

    Returns:
        Enhancement result dictionary
    """
    words = original_text.split()
    correction_list = []
    enhanced_words = words.copy()

    # Simulate some corrections
    for i in range(min(corrections, len(words))):
        if i < len(words):
            original = words[i]
            # Simple simulation: capitalize or fix common typos
            if original.lower() == "teh":
                corrected = "the"
            elif original[0].islower() and i == 0:
                corrected = original.capitalize()
            else:
                corrected = original

            if original != corrected:
                correction_list.append({
                    "original": original,
                    "corrected": corrected,
                    "confidence": 0.95,
                    "issue_type": "spelling" if "teh" in original else "grammar"
                })
                enhanced_words[i] = corrected

    return {
        "enhanced_text": " ".join(enhanced_words),
        "corrections": correction_list,
        "overall_confidence": 0.9,
        "summary": f"Made {len(correction_list)} corrections"
    }


def measure_time(func):
    """
    Decorator to measure function execution time

    Usage:
        @measure_time
        def my_function():
            pass
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.3f} seconds")
        return result
    return wrapper


def generate_document_id() -> str:
    """Generate a unique document ID"""
    timestamp = str(int(time.time()))
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"doc_{timestamp}_{random_str}"


def assert_ocr_response_structure(response: Dict[str, Any], return_format: str = "full"):
    """
    Assert that OCR response has correct structure based on format

    Args:
        response: OCR response dictionary
        return_format: Expected format (full, minimal, ocr_only)
    """
    assert "status" in response

    if return_format == "full":
        # Full response should have all components
        if response.get("quality_check"):
            assert "performed" in response["quality_check"]
            assert "score" in response["quality_check"]

        if response.get("ocr_result"):
            assert "raw_text" in response["ocr_result"]
            assert "confidence_score" in response["ocr_result"]

        assert "confidence_report" in response
        assert "routing_decision" in response["confidence_report"]
        assert "metadata" in response

    elif return_format == "minimal":
        # Minimal response
        assert "extracted_text" in response
        assert "routing_decision" in response
        assert "confidence_score" in response
        assert "document_id" in response

    elif return_format == "ocr_only":
        # OCR only response
        assert "raw_text" in response
        assert "word_count" in response
        assert "ocr_confidence" in response
        assert "processing_time_ms" in response


def mock_async_processing(delay: float = 0.1):
    """
    Create a mock for async processing with delay

    Args:
        delay: Simulated processing delay in seconds
    """
    def async_processor(job_id: str, *args, **kwargs):
        time.sleep(delay)
        return {
            "job_id": job_id,
            "status": "completed",
            "result": create_mock_ocr_response("Sample async result", 0.95)
        }

    return async_processor


def load_test_document(filename: str) -> Optional[bytes]:
    """
    Load a test document from the documents folder

    Args:
        filename: Name of the test document

    Returns:
        Document bytes or None if not found
    """
    doc_path = Path(__file__).parent / "documents" / filename
    if doc_path.exists():
        return doc_path.read_bytes()
    return None


def compare_confidence_scores(score1: float, score2: float, tolerance: float = 0.01) -> bool:
    """
    Compare two confidence scores with tolerance

    Args:
        score1: First score
        score2: Second score
        tolerance: Acceptable difference

    Returns:
        True if scores are within tolerance
    """
    return abs(score1 - score2) <= tolerance


def simulate_ocr_failure() -> Dict[str, Any]:
    """Simulate an OCR processing failure"""
    return {
        "error": "OCR processing failed",
        "error_code": "OCR_FAILURE",
        "details": "Unable to extract text from document"
    }


def simulate_quality_gate_failure() -> Dict[str, Any]:
    """Simulate a quality gate failure"""
    return {
        "quality_check": {
            "performed": True,
            "passed": False,
            "score": 25.0,
            "issues": ["Image too blurry", "Poor contrast", "Low resolution"]
        },
        "status": "failed",
        "error": "Document quality below threshold"
    }