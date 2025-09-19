"""
Basic test to verify test setup
"""

import pytest


def test_basic_setup():
    """Test that pytest is working"""
    assert True


def test_fixtures_available():
    """Test that our fixtures are available"""
    from tests.conftest import sample_png_image
    assert callable(sample_png_image)


def test_utils_available():
    """Test that utils are available"""
    from tests.utils import create_test_image, encode_image_base64
    assert callable(create_test_image)
    assert callable(encode_image_base64)


def test_mock_responses():
    """Test that we can create mock responses"""
    from tests.utils import create_mock_ocr_response, create_mock_quality_assessment

    ocr_resp = create_mock_ocr_response("Test text", 0.95)
    assert "result" in ocr_resp
    assert ocr_resp["result"][0]["ocr_result"]["words_block_list"]

    quality = create_mock_quality_assessment(85.0)
    assert quality["overall_score"] == 85.0
    assert "sharpness_score" in quality


if __name__ == "__main__":
    pytest.main([__file__, "-v"])