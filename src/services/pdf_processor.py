"""
Simplified PDF processor using direct Huawei OCR
"""

import logging
from typing import Dict, Any
from datetime import datetime
from src.services.ocr_service import HuaweiOCRService as OCRService
from src.core.config import settings

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Processes PDF documents directly with Huawei OCR
    Huawei OCR handles PDFs natively - no conversion needed
    """

    def __init__(self):
        self.ocr_service = OCRService()
        self.max_pages_auto = settings.pdf_max_pages_auto_process

    def process_pdf_direct(
        self,
        pdf_bytes: bytes
    ) -> Dict[str, Any]:
        """
        Process PDF directly with Huawei OCR (no conversion needed)
        Huawei OCR supports PDF natively and handles multi-page internally
        """
        result = {
            "status": "processing",
            "text": None,
            "confidence": None,
            "processing_time_ms": None,
            "format": "PDF"
        }

        start_time = datetime.now()

        try:
            # Pass PDF bytes directly to Huawei OCR
            ocr_response = self.ocr_service.process_document(
                file_bytes=pdf_bytes
            )

            # Extract text and confidence
            text = self.ocr_service.extract_text_from_response(ocr_response)
            confidence = self.ocr_service.get_average_confidence(ocr_response)

            result["status"] = "success"
            result["text"] = text
            result["confidence"] = confidence
            result["word_count"] = len(text.split()) if text else 0

        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            result["status"] = "error"
            result["error"] = str(e)

        finally:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            result["processing_time_ms"] = int(processing_time)

        return result

    def process_pdf(
        self,
        pdf_bytes: bytes,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point for PDF processing
        Delegates to process_pdf_direct since Huawei handles PDFs natively
        """
        return self.process_pdf_direct(pdf_bytes)

    # Simplified methods for compatibility with existing code
    def process_all_pages(
        self,
        pdf_bytes: bytes,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Process all pages in a PDF
        Since Huawei handles multi-page PDFs natively, this just calls process_pdf_direct
        """
        return self.process_pdf_direct(pdf_bytes)

    def process_all_pages_parallel(
        self,
        pdf_bytes: bytes,
        max_workers: int = None
    ) -> Dict[str, Any]:
        """
        Process all pages (compatibility method)
        Since Huawei handles PDFs natively, parallel processing is not needed
        """
        result = self.process_pdf_direct(pdf_bytes)

        # Convert to expected format for compatibility
        if result.get("status") == "success":
            return {
                "status": "success",
                "total_pages": 1,  # Huawei returns complete document
                "successful_pages": 1,
                "failed_pages": 0,
                "combined_text": result.get("text", ""),
                "average_confidence": result.get("confidence", 0.0),
                "processing_time_ms": result.get("processing_time_ms", 0)
            }
        else:
            return {
                "status": "failed",
                "total_pages": 0,
                "successful_pages": 0,
                "failed_pages": 0,
                "error": result.get("error", "Processing failed"),
                "processing_time_ms": result.get("processing_time_ms", 0)
            }

    def process_with_progress_callback(
        self,
        pdf_bytes: bytes,
        progress_callback: callable,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Process PDF with progress callback (compatibility method)
        Since processing is a single operation, we just call the callback once
        """
        # Notify start
        progress_callback(1, 1, "processing")

        # Process the PDF
        result = self.process_pdf_direct(pdf_bytes)

        # Notify completion
        status = "success" if result.get("status") == "success" else "error"
        progress_callback(1, 1, status)

        return result

    def process_pdf_page(
        self,
        pdf_bytes: bytes,
        page_number: int = 1,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Process a specific PDF page
        Since Huawei OCR processes the entire PDF, we process all and note the page
        """
        # Huawei OCR doesn't support page-by-page processing
        # So we process the entire PDF and note which page was requested
        result = self.process_pdf_direct(pdf_bytes)

        # Add page information to the result
        if result.get("status") == "success":
            result["page_number"] = page_number
            result["note"] = f"Huawei OCR processes entire PDF. Page {page_number} requested."

            if include_metadata:
                result["metadata"] = {
                    "page_requested": page_number,
                    "processing_note": "Huawei OCR processes complete document"
                }

        return result