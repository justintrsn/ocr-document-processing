"""
Test fixtures and constants for image quality tests

This module contains:
- Paths to test files
- Quality thresholds
- Test configuration
"""

from pathlib import Path
from typing import List
import numpy as np
import cv2
from PIL import Image
from io import BytesIO

from tests.config import test_config

# Test data directories
TEST_ROOT_DIR = Path(__file__).parent.parent
DOCUMENTS_DIR = TEST_ROOT_DIR / "documents"
TEST_IMAGE_PATH = DOCUMENTS_DIR / "scanned_document.jpg"  # Default image

# OBS test paths (same as OCR for consistency)
OBS_TEST_BUCKET = "sample-dataset-bucket"
OBS_TEST_KEY = "OCR/scanned_document.jpg"
OBS_TEST_PREFIX = "OCR/"

# Quality thresholds
QUALITY_THRESHOLDS = {
    "sharpness": {
        "excellent": 80,
        "good": 60,
        "fair": 40,
        "poor": 20
    },
    "contrast": {
        "excellent": 80,
        "good": 60,
        "fair": 40,
        "poor": 20
    },
    "resolution": {
        "excellent": 90,  # 300+ DPI
        "good": 60,      # 200-300 DPI
        "fair": 30,      # 150-200 DPI
        "poor": 0        # <150 DPI
    },
    "noise": {
        "excellent": 90,
        "good": 70,
        "fair": 50,
        "poor": 30
    }
}

# Overall quality threshold for OCR processing
OCR_QUALITY_THRESHOLD = 80.0

# Test configuration
TEST_IMAGE_MAX_SIZE_MB = 10
TEST_IMAGE_OPTIMAL_SIZE_MB = 7
TEST_MIN_DPI = 150
TEST_OPTIMAL_DPI = 300


def get_test_image_bytes() -> bytes:
    """Get test image as bytes"""
    if TEST_IMAGE_PATH.exists():
        return TEST_IMAGE_PATH.read_bytes()
    else:
        # Return a minimal valid JPEG if test image doesn't exist
        return create_minimal_jpeg()


def create_minimal_jpeg() -> bytes:
    """Create a minimal valid JPEG for testing"""
    # Create a small white image
    img = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


def create_sharp_image() -> bytes:
    """Create a sharp test image with text-like patterns"""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 255

    # Add sharp edges and text-like patterns
    cv2.rectangle(img, (100, 100), (700, 500), (0, 0, 0), 2)
    cv2.line(img, (150, 200), (650, 200), (0, 0, 0), 1)
    cv2.line(img, (150, 300), (650, 300), (0, 0, 0), 1)
    cv2.line(img, (150, 400), (650, 400), (0, 0, 0), 1)

    # Add text-like blocks
    for i in range(10):
        x = 150 + i * 50
        cv2.rectangle(img, (x, 250), (x + 30, 270), (0, 0, 0), -1)

    # Convert to bytes
    _, encoded = cv2.imencode('.png', img)
    return encoded.tobytes()


def create_blurry_image() -> bytes:
    """Create a blurry test image"""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (100, 100), (700, 500), (0, 0, 0), 2)

    # Apply heavy blur
    img = cv2.GaussianBlur(img, (25, 25), 10)

    _, encoded = cv2.imencode('.png', img)
    return encoded.tobytes()


def create_low_contrast_image() -> bytes:
    """Create a low contrast test image"""
    # Create image with narrow value range
    img = np.ones((600, 800, 3), dtype=np.uint8) * 128

    # Add low contrast elements
    cv2.rectangle(img, (100, 100), (700, 500), (120, 120, 120), -1)
    cv2.rectangle(img, (200, 200), (600, 400), (136, 136, 136), -1)

    _, encoded = cv2.imencode('.png', img)
    return encoded.tobytes()


def create_noisy_image() -> bytes:
    """Create a noisy test image"""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (100, 100), (700, 500), (0, 0, 0), 2)

    # Add salt and pepper noise
    noise = np.random.random((600, 800, 3))
    img[noise < 0.05] = 0  # Salt
    img[noise > 0.95] = 255  # Pepper

    _, encoded = cv2.imencode('.png', img)
    return encoded.tobytes()


def create_high_dpi_image() -> bytes:
    """Create image with high DPI metadata"""
    img = Image.new('RGB', (800, 600), color='white')

    # Add some content
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 700, 500], outline='black', width=2)

    # Save with DPI information
    buffer = BytesIO()
    img.save(buffer, format='PNG', dpi=(300, 300))
    return buffer.getvalue()


def create_low_dpi_image() -> bytes:
    """Create image with low DPI metadata"""
    img = Image.new('RGB', (800, 600), color='white')

    # Add some content
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 700, 500], outline='black', width=2)

    # Save with low DPI
    buffer = BytesIO()
    img.save(buffer, format='PNG', dpi=(72, 72))
    return buffer.getvalue()


def get_expected_quality_assessment() -> dict:
    """Get expected quality assessment for the test document"""
    return {
        "overall_score": 75.0,
        "quality_level": "good",
        "is_acceptable": True,
        "scores": {
            "sharpness": 70.0,
            "contrast": 75.0,
            "resolution": 80.0,
            "noise": 85.0,
            "brightness": 80.0,
            "orientation": 90.0
        }
    }


def get_all_test_documents() -> List[Path]:
    """Get all test documents based on configuration"""
    documents = []
    for doc_name in test_config.get_test_documents():
        doc_path = DOCUMENTS_DIR / doc_name
        if doc_path.exists():
            documents.append(doc_path)

    if not documents:
        # Fallback to default if no documents configured
        if TEST_IMAGE_PATH.exists():
            documents.append(TEST_IMAGE_PATH)

    return documents


def get_all_test_document_bytes() -> List[tuple[str, bytes]]:
    """Get all test documents as bytes with their names"""
    documents = []
    for doc_path in get_all_test_documents():
        documents.append((doc_path.name, doc_path.read_bytes()))
    return documents


def get_all_obs_test_keys() -> List[str]:
    """Get all OBS test keys from configuration"""
    keys = test_config.get_obs_test_keys()
    return keys if keys else [OBS_TEST_KEY]


def should_test_document(doc_index: int) -> bool:
    """Check if a specific document index should be tested"""
    if test_config.should_test_all_documents():
        return True
    # Only test first document if test_all is False
    return doc_index == 0