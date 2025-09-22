"""
Integration tests for PDF page-by-page processing with Huawei OCR
Tests the critical constraint that PDFs must be processed one page at a time
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import base64
import io
from PIL import Image
import json
from pathlib import Path


@pytest.fixture
def mock_huawei_ocr():
    """Mock Huawei OCR API responses"""
    with patch('src.services.ocr_service.OCRService.process_image') as mock_ocr:
        # Return different text for each page
        mock_ocr.side_effect = lambda img, page_num=None: {
            "status": "success",
            "text": f"Text from page {page_num if page_num else 1}",
            "confidence": 0.95,
            "words": [
                {"text": f"Page{page_num if page_num else 1}", "confidence": 0.98},
                {"text": "content", "confidence": 0.92}
            ]
        }
        yield mock_ocr


@pytest.fixture
def mock_pdf_with_5_pages():
    """Create a mock PDF with 5 pages"""
    from pdf2image import convert_from_bytes
    with patch('pdf2image.convert_from_bytes') as mock_convert:
        # Create 5 mock PIL images
        pages = []
        for i in range(5):
            img = Image.new('RGB', (612, 792), color='white')
            pages.append(img)
        mock_convert.return_value = pages
        yield mock_convert


@pytest.fixture
def mock_pdf_with_corrupted_page():
    """Create a mock PDF where page 3 of 5 is corrupted"""
    with patch('pdf2image.convert_from_bytes') as mock_convert:
        # Create 5 pages, but page 3 raises an error
        pages = []
        for i in range(5):
            if i == 2:  # Page 3 (0-indexed)
                pages.append(None)  # Will cause error
            else:
                img = Image.new('RGB', (612, 792), color='white')
                pages.append(img)
        mock_convert.return_value = pages
        yield mock_convert


class TestPDFPageProcessing:
    """Test PDF page-by-page processing integration"""

    def test_single_page_pdf_processing(self, mock_huawei_ocr):
        """Test processing a single page from a PDF"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Process only page 2
        result = processor.process_pdf_page(
            pdf_bytes=b"fake_pdf_content",
            page_number=2
        )

        assert result["status"] == "success"
        assert result["page_number"] == 2
        assert "Text from page 2" in result["text"]

        # Verify OCR was called once for the specific page
        assert mock_huawei_ocr.call_count == 1

    def test_all_pages_pdf_processing(self, mock_huawei_ocr, mock_pdf_with_5_pages):
        """Test processing all pages makes separate API calls"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Process all pages
        result = processor.process_all_pages(
            pdf_bytes=b"fake_pdf_content"
        )

        assert result["status"] == "success"
        assert result["total_pages"] == 5
        assert len(result["page_results"]) == 5

        # Verify separate API call for each page
        assert mock_huawei_ocr.call_count == 5

        # Verify each page has its own result
        for i in range(5):
            page_result = result["page_results"][i + 1]
            assert page_result["status"] == "success"
            assert f"Text from page {i + 1}" in page_result["text"]

    def test_partial_failure_recovery(self, mock_huawei_ocr, mock_pdf_with_corrupted_page):
        """Test handling when page 3 of 5 is corrupted"""
        from src.services.pdf_processor import PDFProcessor

        # Mock OCR to fail on corrupted page
        def ocr_side_effect(img, page_num=None):
            if img is None:
                raise ValueError("Corrupted page")
            return {
                "status": "success",
                "text": f"Text from page {page_num}",
                "confidence": 0.95
            }

        mock_huawei_ocr.side_effect = ocr_side_effect

        processor = PDFProcessor()

        # Process all pages with partial failure
        result = processor.process_all_pages(
            pdf_bytes=b"fake_pdf_content",
            continue_on_error=True
        )

        assert result["status"] == "partial_success"
        assert result["total_pages"] == 5
        assert result["successful_pages"] == [1, 2, 4, 5]
        assert result["failed_pages"] == [3]

        # Page 3 should have error details
        assert result["page_results"][3]["status"] == "error"
        assert "Corrupted page" in result["page_results"][3]["error"]

        # Other pages should succeed
        for page_num in [1, 2, 4, 5]:
            assert result["page_results"][page_num]["status"] == "success"

    def test_pdf_page_range_processing(self, mock_huawei_ocr, mock_pdf_with_5_pages):
        """Test processing a specific range of pages"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Process pages 2-4
        result = processor.process_page_range(
            pdf_bytes=b"fake_pdf_content",
            start_page=2,
            end_page=4
        )

        assert result["status"] == "success"
        assert result["pages_processed"] == 3
        assert len(result["page_results"]) == 3

        # Verify only 3 OCR calls were made
        assert mock_huawei_ocr.call_count == 3

        # Results should be for pages 2, 3, 4
        assert 2 in result["page_results"]
        assert 3 in result["page_results"]
        assert 4 in result["page_results"]
        assert 1 not in result["page_results"]
        assert 5 not in result["page_results"]

    def test_pdf_parallel_page_processing(self, mock_huawei_ocr, mock_pdf_with_5_pages):
        """Test parallel processing with limit of 4 workers"""
        from src.services.pdf_processor import PDFProcessor
        from concurrent.futures import ThreadPoolExecutor
        import time

        processor = PDFProcessor()

        # Add delay to mock OCR to simulate processing time
        original_side_effect = mock_huawei_ocr.side_effect

        def delayed_ocr(*args, **kwargs):
            time.sleep(0.1)  # 100ms per page
            return original_side_effect(*args, **kwargs)

        mock_huawei_ocr.side_effect = delayed_ocr

        start_time = time.time()

        # Process with parallel workers
        result = processor.process_all_pages_parallel(
            pdf_bytes=b"fake_pdf_content",
            max_workers=4
        )

        end_time = time.time()
        processing_time = end_time - start_time

        assert result["status"] == "success"
        assert result["total_pages"] == 5

        # With 4 workers, 5 pages should take ~200ms (2 batches)
        # Without parallel, would take ~500ms
        # This is approximate due to overhead
        assert processing_time < 0.4  # Should be faster than sequential

        # All pages should be processed
        assert mock_huawei_ocr.call_count == 5

    def test_pdf_page_metadata_extraction(self, mock_huawei_ocr):
        """Test extraction of page-level metadata"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Mock page info extraction
        with patch.object(processor, 'extract_page_info') as mock_info:
            mock_info.return_value = {
                "page_number": 1,
                "width": 612,
                "height": 792,
                "rotation": 0,
                "has_text": True,
                "has_images": False
            }

            result = processor.process_pdf_page(
                pdf_bytes=b"fake_pdf_content",
                page_number=1,
                include_metadata=True
            )

            assert result["status"] == "success"
            assert "metadata" in result
            assert result["metadata"]["width"] == 612
            assert result["metadata"]["height"] == 792
            assert result["metadata"]["rotation"] == 0

    def test_pdf_auto_retry_on_failure(self, mock_huawei_ocr):
        """Test automatic retry for failed pages"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # First call fails, second succeeds
        mock_huawei_ocr.side_effect = [
            Exception("Temporary OCR failure"),
            {
                "status": "success",
                "text": "Text after retry",
                "confidence": 0.93
            }
        ]

        result = processor.process_pdf_page(
            pdf_bytes=b"fake_pdf_content",
            page_number=1,
            retry_on_failure=True,
            max_retries=2
        )

        assert result["status"] == "success"
        assert "Text after retry" in result["text"]
        assert result["retry_count"] == 1

        # OCR should be called twice (initial + 1 retry)
        assert mock_huawei_ocr.call_count == 2

    def test_pdf_page_size_validation(self):
        """Test validation of page size before OCR"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Create oversized page
        oversized_img = Image.new('RGB', (50000, 50000), color='white')

        with patch('pdf2image.convert_from_bytes') as mock_convert:
            mock_convert.return_value = [oversized_img]

            result = processor.process_pdf_page(
                pdf_bytes=b"fake_pdf_content",
                page_number=1
            )

            assert result["status"] == "error"
            assert "DIMENSIONS_INVALID" in result["error_code"]
            assert "exceeds maximum" in result["error"].lower()

    def test_pdf_processing_with_timeout(self, mock_huawei_ocr):
        """Test timeout handling for slow page processing"""
        from src.services.pdf_processor import PDFProcessor
        import time

        processor = PDFProcessor()

        # Mock slow OCR processing
        def slow_ocr(*args, **kwargs):
            time.sleep(5)  # 5 seconds (will timeout)
            return {"status": "success", "text": "Should timeout"}

        mock_huawei_ocr.side_effect = slow_ocr

        result = processor.process_pdf_page(
            pdf_bytes=b"fake_pdf_content",
            page_number=1,
            timeout_seconds=1  # 1 second timeout
        )

        assert result["status"] == "error"
        assert "TIMEOUT" in result["error_code"]

    def test_pdf_page_order_preservation(self, mock_huawei_ocr, mock_pdf_with_5_pages):
        """Test that pages are processed in correct order even with parallel processing"""
        from src.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        result = processor.process_all_pages_parallel(
            pdf_bytes=b"fake_pdf_content",
            max_workers=4
        )

        assert result["status"] == "success"

        # Verify pages are in correct order
        page_numbers = list(result["page_results"].keys())
        assert page_numbers == [1, 2, 3, 4, 5]

        # Verify content matches page number
        for page_num in range(1, 6):
            assert f"Text from page {page_num}" in result["page_results"][page_num]["text"]