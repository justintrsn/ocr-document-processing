"""
Test fixtures and constants for OCR tests

This module contains:
- Paths to test files
- Sample OCR responses
- Test configuration
"""

from pathlib import Path

# Test data directories
TEST_ROOT_DIR = Path(__file__).parent.parent
DOCUMENTS_DIR = TEST_ROOT_DIR / "documents"
TEST_IMAGE_PATH = DOCUMENTS_DIR / "scanned_document.jpg"

# OBS test paths
OBS_TEST_BUCKET = "sample-dataset-bucket"
OBS_TEST_KEY = "OCR/scanned_document.jpg"
OBS_TEST_PREFIX = "OCR/"

# Sample OCR response for mocking
SAMPLE_OCR_RESPONSE = {
    "result": [{
        "ocr_result": {
            "words_block_list": [
                {
                    "words": "Medical Certificate",
                    "confidence": 0.98,
                    "location": [[10, 10], [200, 10], [200, 30], [10, 30]]
                },
                {
                    "words": "Patient Name: John Doe",
                    "confidence": 0.95,
                    "location": [[10, 40], [250, 40], [250, 60], [10, 60]]
                },
                {
                    "words": "Date: 2025-01-18",
                    "confidence": 0.97,
                    "location": [[10, 70], [150, 70], [150, 90], [10, 90]]
                }
            ],
            "direction": 0.0,
            "words_block_count": 3
        },
        "kv_result": {
            "kv_block_count": 2,
            "kv_block_list": [
                {
                    "key": "Patient Name",
                    "value": "John Doe",
                    "words_block_count": 1,
                    "words_block_list": []
                },
                {
                    "key": "Date",
                    "value": "2025-01-18",
                    "words_block_count": 1,
                    "words_block_list": []
                }
            ]
        }
    }]
}

# Test configuration
TEST_CONFIDENCE_THRESHOLD = 80.0
TEST_IMAGE_MAX_SIZE_MB = 10
TEST_IMAGE_OPTIMAL_SIZE_MB = 7

# Expected text from test document
EXPECTED_DOCUMENT_TEXT = """HeartlandHealthC
■ 6547-884088 Circuit Road #01-965Singapore 370088
MEDICAL CERTIFICATE"""

# Test API endpoints
TEST_OCR_ENDPOINT = "https://ocr.ap-southeast-3.myhuaweicloud.com"
TEST_PROJECT_ID = "test_project_id"


def get_test_image_bytes() -> bytes:
    """Get test image as bytes"""
    if TEST_IMAGE_PATH.exists():
        return TEST_IMAGE_PATH.read_bytes()
    else:
        # Return a minimal valid JPEG if test image doesn't exist
        # This is a 1x1 white pixel JPEG
        return bytes.fromhex(
            'ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707'
            '070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c'
            '1c28372c2c303336281a2a393a393a2c323738362effdb0043010909090c0b0c180d'
            '0d1832211c213232323232323232323232323232323232323232323232323232'
            '3232323232323232323232323232323232323232323232323232ffc0001108000100'
            '0103012200021101031101ffc4001f000001050101010101010000000000000001'
            '0203040506070809ffd9'
        )


def get_sample_ocr_response_for_confidence(confidence: float) -> dict:
    """Generate a sample OCR response with specific confidence level"""
    return {
        "result": [{
            "ocr_result": {
                "words_block_list": [
                    {
                        "words": "Test Document",
                        "confidence": confidence,
                        "location": [[10, 10], [100, 10], [100, 30], [10, 30]]
                    }
                ],
                "direction": 0.0,
                "words_block_count": 1
            }
        }]
    }