"""
Test OCR with local test image

This test demonstrates using the local test image stored in tests/ocr/
for quick local testing without OBS dependency.
"""

import pytest
from pathlib import Path

from tests.ocr.fixtures import TEST_IMAGE_PATH, EXPECTED_DOCUMENT_TEXT


@pytest.mark.skipif(
    not TEST_IMAGE_PATH.exists(),
    reason="Test image not found in tests/ocr/"
)
def test_local_image_exists():
    """Verify test image exists and is valid"""
    assert TEST_IMAGE_PATH.exists(), f"Test image not found at {TEST_IMAGE_PATH}"

    # Check file size
    size_mb = TEST_IMAGE_PATH.stat().st_size / (1024 * 1024)
    assert size_mb < 10, f"Test image too large: {size_mb:.2f}MB (max 10MB)"

    # Check file extension
    assert TEST_IMAGE_PATH.suffix.lower() in ['.jpg', '.jpeg', '.png'], \
        f"Invalid file type: {TEST_IMAGE_PATH.suffix}"

    print(f"\n✅ Test image found: {TEST_IMAGE_PATH}")
    print(f"   Size: {size_mb:.2f}MB")


@pytest.mark.integration
@pytest.mark.skipif(
    not TEST_IMAGE_PATH.exists(),
    reason="Test image not found"
)
def test_ocr_with_local_image(mock_ocr_service):
    """Test OCR processing with local test image"""
    from unittest.mock import patch, Mock

    # Mock the actual API call but use real image processing
    with patch('src.services.ocr_service.requests.post') as mock_post:
        # Mock token response
        mock_token = Mock()
        mock_token.status_code = 201
        mock_token.headers = {'X-Subject-Token': 'test_token'}

        # Mock OCR response
        mock_ocr = Mock()
        mock_ocr.status_code = 200
        mock_ocr.json.return_value = {
            "result": [{
                "ocr_result": {
                    "words_block_list": [
                        {"words": "Test successful", "confidence": 0.99}
                    ]
                }
            }]
        }

        mock_post.side_effect = [mock_token, mock_ocr]

        # Process the test image
        result = mock_ocr_service.process_document(TEST_IMAGE_PATH)

        # Verify the image was processed
        assert result is not None
        assert result.result is not None

        # Check that base64 encoding was used
        ocr_call = mock_post.call_args_list[1]
        request_json = ocr_call[1]['json']
        assert 'data' in request_json  # Should use base64 mode
        assert len(request_json['data']) > 1000  # Should have base64 content


def test_reference_paths():
    """Test that all reference paths are correct"""
    from tests.ocr.fixtures import (
        TEST_ROOT_DIR,
        DOCUMENTS_DIR,
        TEST_IMAGE_PATH,
        OBS_TEST_KEY
    )

    # Check that test directories are correct
    assert TEST_ROOT_DIR.name == "tests"
    assert DOCUMENTS_DIR.name == "documents"
    assert DOCUMENTS_DIR.parent == TEST_ROOT_DIR

    # Check image path
    assert TEST_IMAGE_PATH.name == "scanned_document.jpg"
    assert TEST_IMAGE_PATH.parent == DOCUMENTS_DIR

    # Check OBS reference
    assert OBS_TEST_KEY == "OCR/scanned_document.jpg"

    print(f"\n✅ All reference paths are correct")
    print(f"   Test root: {TEST_ROOT_DIR}")
    print(f"   Documents dir: {DOCUMENTS_DIR}")
    print(f"   Image: {TEST_IMAGE_PATH}")
    print(f"   OBS key: {OBS_TEST_KEY}")