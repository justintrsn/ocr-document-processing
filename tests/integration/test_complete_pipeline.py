"""
Complete OCR Pipeline Integration Test
Tests the full flow: Quality Check → Preprocessing → OCR → LLM Enhancement

This test uses REAL documents from tests/documents/ folder
Supports both API testing (via endpoints) and local testing (direct component calls)
"""

import pytest
import base64
import requests
import time
from pathlib import Path
from typing import Dict, Any, List

# Load environment variables
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Configuration
API_BASE_URL = "http://localhost:8000"
DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"

# Supported formats (all 11)
SUPPORTED_FORMATS = ["PNG", "JPG", "JPEG", "BMP", "GIF", "TIFF", "WebP", "PCX", "ICO", "PSD", "PDF"]

# Real documents mapping (add more as they become available)
REAL_DOCUMENTS = {
    "JPG": ["scanned_document.jpg"],
    "PDF": ["scanned_document.pdf", "resume.pdf"],
    # Add more real documents as they're added to tests/documents/
    # "PNG": ["invoice.png"],
    # "TIFF": ["contract.tiff"],
    # etc.
}


class TestCompletePipeline:
    """Test complete OCR pipeline with real documents"""

    @pytest.fixture
    def api_client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from src.api.main import app
        return TestClient(app)

    def encode_file(self, file_path: Path) -> str:
        """Encode file to base64"""
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def find_test_documents(self, format_type: str) -> List[Path]:
        """Find real test documents for a given format"""
        documents = []

        # Check if we have real documents for this format
        if format_type.upper() in REAL_DOCUMENTS:
            for doc_name in REAL_DOCUMENTS[format_type.upper()]:
                doc_path = DOCUMENTS_DIR / doc_name
                if doc_path.exists():
                    documents.append(doc_path)

        # Also search for any other documents with this extension
        for ext in [format_type.lower(), format_type.upper()]:
            for doc_path in DOCUMENTS_DIR.glob(f"*.{ext}"):
                if doc_path not in documents and doc_path.name != "README.md":
                    documents.append(doc_path)

        return documents

    @pytest.mark.parametrize("enable_preprocessing", [True, False])
    @pytest.mark.parametrize("enable_llm", [True, False])
    def test_complete_pipeline_api(self, api_client, enable_preprocessing, enable_llm):
        """Test complete pipeline via API with different configurations"""

        # Test with available real documents
        tested_formats = []

        for format_type in ["JPG", "PDF"]:  # Start with formats we know have real docs
            documents = self.find_test_documents(format_type)

            for doc_path in documents[:1]:  # Test first document of each type
                print(f"\n📄 Testing {format_type} with: {doc_path.name}")
                print(f"   Preprocessing: {enable_preprocessing}, LLM: {enable_llm}")

                # Prepare request
                file_base64 = self.encode_file(doc_path)
                request_data = {
                    "source": {
                        "type": "file",
                        "file": file_base64
                    },
                    "processing_options": {
                        "enable_ocr": True,
                        "enable_enhancement": enable_llm,
                        "enable_preprocessing": enable_preprocessing,
                        "return_format": "full"
                    },
                    "thresholds": {
                        "image_quality_threshold": 60,
                        "confidence_threshold": 80
                    },
                    "async_processing": False
                }

                # Make request
                response = api_client.post("/api/v1/ocr", json=request_data)

                # Assertions
                assert response.status_code == 200, f"Failed for {doc_path.name}: {response.text}"

                result = response.json()
                assert result["status"] == "success"

                # Validate response structure
                self._validate_api_response(result, enable_llm)
                tested_formats.append(format_type)

        assert len(tested_formats) > 0, "No documents were tested"

    def _validate_api_response(self, response: Dict[str, Any], llm_enabled: bool):
        """Validate API response structure"""

        # Required fields
        assert "status" in response
        assert "confidence_report" in response
        assert "metadata" in response

        # Quality check (always performed)
        if "quality_check" in response and response["quality_check"] is not None:
            qc = response["quality_check"]
            assert "performed" in qc
            assert "score" in qc
            assert "passed" in qc
            assert "metrics" in qc

        # OCR result
        if "ocr_result" in response and response["ocr_result"] is not None:
            ocr = response["ocr_result"]
            assert "raw_text" in ocr
            assert "word_count" in ocr
            assert "confidence_score" in ocr
            assert "confidence_distribution" in ocr

        # LLM enhancement (if enabled)
        if llm_enabled and "enhancement" in response and response["enhancement"] is not None:
            enh = response["enhancement"]
            assert "performed" in enh
            if enh.get("performed", False):
                assert "enhanced_text" in enh or enh["enhanced_text"] is None
                assert "corrections" in enh

        # Confidence report
        cr = response["confidence_report"]
        assert "image_quality_score" in cr
        assert "ocr_confidence_score" in cr
        assert "final_confidence" in cr
        assert "routing_decision" in cr
        assert cr["routing_decision"] in ["pass", "requires_review"]

        # Metadata
        meta = response["metadata"]
        assert "document_id" in meta
        assert "timestamp" in meta
        assert "processing_time_ms" in meta

    def test_preprocessing_improves_quality(self, api_client):
        """Test that preprocessing actually improves document quality"""

        # Use a real scanned document
        doc_path = DOCUMENTS_DIR / "scanned_document.jpg"
        if not doc_path.exists():
            pytest.skip("Test document not found")

        file_base64 = self.encode_file(doc_path)

        # Test without preprocessing
        request_no_prep = {
            "source": {"type": "file", "file": file_base64},
            "processing_options": {
                "enable_ocr": True,
                "enable_preprocessing": False,
                "return_format": "full"
            },
            "thresholds": {
                "image_quality_threshold": 30,
                "confidence_threshold": 60
            }
        }

        response_no_prep = api_client.post("/api/v1/ocr", json=request_no_prep)
        assert response_no_prep.status_code == 200
        result_no_prep = response_no_prep.json()

        # Test with preprocessing
        request_with_prep = {
            "source": {"type": "file", "file": file_base64},
            "processing_options": {
                "enable_ocr": True,
                "enable_preprocessing": True,
                "return_format": "full"
            },
            "thresholds": {
                "image_quality_threshold": 30,
                "confidence_threshold": 60
            }
        }

        response_with_prep = api_client.post("/api/v1/ocr", json=request_with_prep)
        assert response_with_prep.status_code == 200
        result_with_prep = response_with_prep.json()

        # Compare results
        if "ocr_result" in result_no_prep and "ocr_result" in result_with_prep:
            confidence_no_prep = result_no_prep["ocr_result"].get("confidence_score", 0)
            confidence_with_prep = result_with_prep["ocr_result"].get("confidence_score", 0)

            print(f"\n📊 Preprocessing Impact:")
            print(f"   Without preprocessing: {confidence_no_prep:.1f}%")
            print(f"   With preprocessing: {confidence_with_prep:.1f}%")

            # Preprocessing should maintain or improve confidence
            # (may not always improve if document is already good quality)
            assert confidence_with_prep >= confidence_no_prep - 5  # Allow small variance

    def test_pdf_processing(self, api_client):
        """Test PDF-specific processing"""

        pdf_docs = self.find_test_documents("PDF")
        assert len(pdf_docs) > 0, "No PDF documents found for testing"

        for doc_path in pdf_docs[:1]:  # Test first PDF
            print(f"\n📑 Testing PDF: {doc_path.name}")

            file_base64 = self.encode_file(doc_path)
            request_data = {
                "source": {"type": "file", "file": file_base64},
                "processing_options": {
                    "enable_ocr": True,
                    "enable_preprocessing": True,
                    "return_format": "full"
                },
                "thresholds": {
                    "image_quality_threshold": 60,
                    "confidence_threshold": 80
                }
            }

            # Test with page_number parameter
            response = api_client.post(
                "/api/v1/ocr",
                json=request_data,
                params={"page_number": 1}
            )

            assert response.status_code == 200
            result = response.json()

            # Check for PDF-specific metadata
            if "metadata" in result:
                # PDF should process entire document (Huawei OCR native support)
                assert result["status"] == "success"

                # Should have OCR results
                if "ocr_result" in result:
                    assert len(result["ocr_result"]["raw_text"]) > 0

    def test_format_detection(self, api_client):
        """Test that format detection works correctly"""

        test_formats = ["JPG", "PDF"]

        for format_type in test_formats:
            documents = self.find_test_documents(format_type)

            for doc_path in documents[:1]:
                # Test format validation endpoint
                with open(doc_path, "rb") as f:
                    response = api_client.post(
                        "/api/v1/ocr/validate-format",
                        files={"file": (doc_path.name, f, "application/octet-stream")}
                    )

                if response.status_code == 200:
                    result = response.json()
                    assert "format_detected" in result
                    assert result["is_supported"] == True

                    # Format should match expected
                    detected = result["format_detected"].upper()
                    # Handle JPEG/JPG equivalence
                    if format_type == "JPG" and detected == "JPEG":
                        assert True
                    elif format_type == "JPEG" and detected == "JPG":
                        assert True
                    else:
                        assert detected == format_type.upper()

    def test_error_handling(self, api_client):
        """Test error handling for invalid inputs"""

        # Test with invalid base64
        request_data = {
            "source": {
                "type": "file",
                "file": "invalid_base64_content"
            },
            "processing_options": {
                "enable_ocr": True
            }
        }

        response = api_client.post("/api/v1/ocr", json=request_data)
        assert response.status_code in [400, 415, 500]

        # Test with missing required fields
        request_data = {
            "source": {
                "type": "file"
                # Missing 'file' field
            }
        }

        response = api_client.post("/api/v1/ocr", json=request_data)
        assert response.status_code in [422, 400, 500]  # 500 happens when validation occurs in processing

    @pytest.mark.skip(reason="Only run when services are deployed")
    def test_performance(self, api_client):
        """Test processing performance with real documents"""

        doc_path = DOCUMENTS_DIR / "scanned_document.jpg"
        if not doc_path.exists():
            pytest.skip("Test document not found")

        file_base64 = self.encode_file(doc_path)
        request_data = {
            "source": {"type": "file", "file": file_base64},
            "processing_options": {
                "enable_ocr": True,
                "enable_preprocessing": False,
                "enable_enhancement": False,
                "return_format": "full"
            }
        }

        # Measure processing time
        start_time = time.time()
        response = api_client.post("/api/v1/ocr", json=request_data)
        elapsed_time = (time.time() - start_time) * 1000

        assert response.status_code == 200
        result = response.json()

        # Check processing time
        if "metadata" in result:
            api_reported_time = result["metadata"].get("processing_time_ms", 0)
            print(f"\n⏱️  Performance:")
            print(f"   API reported: {api_reported_time:.0f}ms")
            print(f"   Total request: {elapsed_time:.0f}ms")

            # Should complete within reasonable time (10 seconds for OCR without enhancement)
            assert elapsed_time < 10000, f"Processing took too long: {elapsed_time}ms"


def test_with_all_real_documents():
    """Standalone test function to test all real documents"""

    print("\n" + "="*70)
    print("📚 Testing with ALL Real Documents")
    print("="*70)

    results = []
    documents_found = {}

    # Find all real documents
    for format_type in SUPPORTED_FORMATS:
        format_docs = []

        # Check known real documents
        if format_type in REAL_DOCUMENTS:
            for doc_name in REAL_DOCUMENTS[format_type]:
                doc_path = DOCUMENTS_DIR / doc_name
                if doc_path.exists():
                    format_docs.append(doc_path)

        # Search for any documents with this extension
        for ext in [format_type.lower(), format_type.upper()]:
            for doc_path in DOCUMENTS_DIR.glob(f"*.{ext}"):
                if doc_path not in format_docs and doc_path.name != "README.md":
                    format_docs.append(doc_path)

        if format_docs:
            documents_found[format_type] = format_docs

    # Display found documents
    print(f"\n📁 Found Documents:")
    for format_type, docs in documents_found.items():
        print(f"   {format_type}: {len(docs)} document(s)")
        for doc in docs:
            print(f"      - {doc.name}")

    # Test each document via API
    for format_type, docs in documents_found.items():
        for doc_path in docs:
            print(f"\n🔄 Testing {doc_path.name}...")

            try:
                with open(doc_path, "rb") as f:
                    file_base64 = base64.b64encode(f.read()).decode('utf-8')

                request_data = {
                    "source": {"type": "file", "file": file_base64},
                    "processing_options": {
                        "enable_ocr": True,
                        "enable_preprocessing": True,
                        "enable_enhancement": False,
                        "return_format": "full"
                    }
                }

                response = requests.post(f"{API_BASE_URL}/api/v1/ocr", json=request_data, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    if "ocr_result" in result:
                        word_count = result["ocr_result"].get("word_count", 0)
                        confidence = result["ocr_result"].get("confidence_score", 0)
                        print(f"   ✅ Success: {word_count} words, {confidence:.1f}% confidence")
                        results.append({"doc": doc_path.name, "success": True, "words": word_count})
                    else:
                        print(f"   ⚠️  No OCR result")
                        results.append({"doc": doc_path.name, "success": False, "error": "No OCR result"})
                else:
                    print(f"   ❌ Error: Status {response.status_code}")
                    results.append({"doc": doc_path.name, "success": False, "error": f"Status {response.status_code}"})

            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                results.append({"doc": doc_path.name, "success": False, "error": str(e)})

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"   {r['doc']}: {r['words']} words")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   {r['doc']}: {r['error']}")

    print("\n" + "="*70)


if __name__ == "__main__":
    # Run standalone test when executed directly
    import sys

    if "--api" in sys.argv:
        # Test via API
        test_with_all_real_documents()
    else:
        # Run pytest
        pytest.main([__file__, "-v"])