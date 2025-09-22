# OCR Document Processing API Documentation

## Overview

The OCR Document Processing API provides a comprehensive endpoint for document analysis with quality assessment, preprocessing, OCR extraction, and optional LLM enhancement. The system supports **11 file formats** and implements a dual-threshold routing system for automatic quality control.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. In production, implement API key or OAuth2 authentication.

## Supported File Formats

The API natively supports the following 11 formats through Huawei Cloud OCR:
- **Images**: PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, PCX, ICO, PSD
- **Documents**: PDF

All formats are processed directly without conversion.

## Main Endpoints

### 1. Process Document

**Endpoint**: `POST /api/v1/ocr`

**Description**: Processes a document through the complete OCR pipeline with configurable options.

#### Request Body

```json
{
  "source": {
    "type": "file" | "obs_url",
    "file": "base64_encoded_string",  // if type=file
    "obs_url": "obs://bucket/path"     // if type=obs_url
  },
  "processing_options": {
    "enable_ocr": true,                // Default: true
    "enable_enhancement": false,       // Default: false (LLM enhancement)
    "enable_preprocessing": true,      // Default: true (image preprocessing)
    "return_format": "full"            // Options: "full", "minimal", "ocr_only"
  },
  "thresholds": {
    "image_quality_threshold": 60.0,   // Default: 60, Range: 0-100
    "confidence_threshold": 80.0       // Default: 80, Range: 0-100
  },
  "async_processing": false            // Default: false
}
```

#### Query Parameters (Optional)

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_number` | Integer | Specific page number for PDF processing (1-indexed) |
| `process_all_pages` | Boolean | Process all pages for PDF (default: false) |
| `auto_rotation` | Boolean | Apply automatic rotation detection (default: true) |
| `format_validation` | Boolean | Validate file format before processing (default: true) |
| `preprocessing_quality_threshold` | Float | Override quality threshold for preprocessing |

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | Object | Yes | Document input source |
| `source.type` | String | Yes | Either "file" or "obs_url" |
| `source.file` | String | Conditional | Base64 encoded file content (required if type="file") |
| `source.obs_url` | String | Conditional | OBS URL (required if type="obs_url") |
| `processing_options` | Object | No | Processing configuration |
| `processing_options.enable_ocr` | Boolean | No | Enable OCR extraction (default: true) |
| `processing_options.enable_enhancement` | Boolean | No | Enable LLM enhancement (default: false) |
| `processing_options.enable_preprocessing` | Boolean | No | Enable preprocessing for quality improvement (default: true) |
| `processing_options.return_format` | String | No | Response format: "full", "minimal", or "ocr_only" (default: "full") |
| `thresholds` | Object | No | Threshold settings |
| `thresholds.image_quality_threshold` | Float | No | Minimum quality to proceed with OCR (default: 60) |
| `thresholds.confidence_threshold` | Float | No | Minimum confidence for automatic routing (default: 80) |
| `async_processing` | Boolean | No | Process asynchronously (default: false) |

#### Response Formats

##### Full Response (return_format="full")

```json
{
  "status": "success",
  "job_id": null,
  "quality_check": {
    "performed": true,
    "passed": true,
    "score": 82.5,
    "metrics": {
      "sharpness": 85.0,
      "contrast": 80.0,
      "resolution": 82.0,
      "noise_level": 5.0
    },
    "issues": [],
    "processing_time_ms": 100.5
  },
  "ocr_result": {
    "raw_text": "Extracted text content...",
    "word_count": 150,
    "confidence_score": 94.5,
    "confidence_distribution": {
      "high": 120,
      "medium": 25,
      "low": 5,
      "very_low": 0
    },
    "raw_response": null,
    "processing_time_ms": 1500.0
  },
  "enhancement": {
    "performed": true,
    "enhanced_text": "Corrected and improved text...",
    "corrections": [
      {
        "original": "teh",
        "corrected": "the",
        "confidence": 0.95,
        "type": "spelling"
      }
    ],
    "processing_time_ms": 20000.0,
    "tokens_used": 1500
  },
  "confidence_report": {
    "image_quality_score": 82.5,
    "ocr_confidence_score": 94.5,
    "final_confidence": 88.5,
    "thresholds_applied": {
      "image_quality_threshold": 60.0,
      "confidence_threshold": 80.0
    },
    "routing_decision": "pass",
    "routing_reason": "All thresholds met",
    "quality_check_passed": true,
    "confidence_check_passed": true
  },
  "metadata": {
    "document_id": "doc_abc123def456",
    "timestamp": "2025-01-19T10:30:00Z",
    "version": "1.0",
    "processing_time_ms": 22000.0
  }
}
```

##### Minimal Response (return_format="minimal")

```json
{
  "status": "success",
  "extracted_text": "Final processed text...",
  "routing_decision": "pass",
  "confidence_score": 88.5,
  "document_id": "doc_abc123def456"
}
```

##### OCR Only Response (return_format="ocr_only")

```json
{
  "status": "success",
  "raw_text": "OCR extracted text...",
  "word_count": 150,
  "ocr_confidence": 94.5,
  "processing_time_ms": 1600.0,
  "document_id": "doc_abc123def456"
}
```

##### Async Response (async_processing=true)

```json
{
  "status": "accepted",
  "job_id": "job_xyz789ghi012",
  "message": "Document submitted for processing",
  "estimated_time_seconds": 30
}
```

#### Error Responses

```json
{
  "detail": {
    "error_code": "FORMAT_NOT_SUPPORTED",
    "message": "Format validation failed",
    "format_detected": "XYZ"
  }
}
```

Common error codes:
- `400` - Invalid request (bad base64, missing required fields)
- `413` - Payload too large (file exceeds 10MB)
- `415` - Unsupported media type (format not supported)
- `422` - Validation error (invalid parameter values)
- `500` - Internal server error

### 2. Preprocessing Endpoint

**Endpoint**: `POST /api/v1/preprocess`

**Description**: Preprocesses a document to improve OCR quality.

#### Request Body

```json
{
  "source_type": "file",
  "file_data": "base64_encoded_string",
  "quality_threshold": 80.0,
  "save_to_obs": false
}
```

### 3. Format Validation

**Endpoint**: `POST /api/v1/ocr/validate-format`

**Description**: Validates file format and returns capabilities.

#### Request

Multipart form data with file upload.

#### Response

```json
{
  "format_detected": "PDF",
  "is_supported": true,
  "validation_errors": null,
  "capabilities": {
    "can_extract_text": true,
    "can_extract_tables": true,
    "can_extract_kv_pairs": true,
    "supports_rotation": true,
    "multi_page": true
  }
}
```

### 4. Supported Formats List

**Endpoint**: `GET /api/v1/ocr/supported-formats`

**Description**: Get list of all supported formats with their capabilities.

#### Response

```json
{
  "supported_formats": ["PNG", "JPG", "JPEG", "BMP", "GIF", "TIFF", "WebP", "PCX", "ICO", "PSD", "PDF"],
  "total_formats": 11,
  "format_details": {
    "PNG": {
      "can_extract_text": true,
      "can_extract_tables": true,
      "can_extract_kv_pairs": true,
      "supports_rotation": true,
      "multi_page": false
    },
    "PDF": {
      "can_extract_text": true,
      "can_extract_tables": true,
      "can_extract_kv_pairs": true,
      "supports_rotation": true,
      "multi_page": true
    }
  }
}
```

### 5. Batch Processing

**Endpoint**: `POST /api/v1/batch`

**Description**: Process multiple documents (up to 20) in a single request.

### 6. Processing History

**Endpoint**: `GET /api/v1/ocr/history/{document_id}`

**Description**: Retrieve processing history for a document (stored for 7 days).

### 7. Async Job Status

**Endpoint**: `GET /api/v1/ocr/job/{job_id}`

**Description**: Retrieves the status and results of an asynchronous OCR job.

### 8. Health Check

**Endpoint**: `GET /health`

**Description**: Check API health status.

## Processing Pipeline

### Complete Flow

```
Document Input → Format Detection → Quality Check → Preprocessing → OCR → LLM Enhancement → Response
```

### Stage Details

1. **Format Detection**: Validates file format (11 supported formats)
2. **Quality Check**: Always performed first, scores image quality
3. **Preprocessing** (Optional): Applied if quality < threshold and enabled
   - Noise reduction
   - Contrast enhancement
   - Rotation correction
   - Sharpening
4. **OCR Processing**: Huawei Cloud OCR extracts text
5. **LLM Enhancement** (Optional): Improves text quality with AI
6. **Routing Decision**: Determines if manual review is needed

### PDF Processing

PDFs are processed as complete documents by Huawei OCR:
- **Default**: Process entire PDF
- **Page-specific**: Use `page_number` parameter
- **Note**: Huawei OCR processes the complete PDF regardless of page parameter

## Usage Examples

### Example 1: Quick OCR with Preprocessing

```bash
# Encode file
IMAGE_BASE64=$(base64 -w 0 document.jpg)

# Send request
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "file",
      "file": "'"$IMAGE_BASE64"'"
    },
    "processing_options": {
      "enable_ocr": true,
      "enable_enhancement": false,
      "enable_preprocessing": true,
      "return_format": "ocr_only"
    },
    "thresholds": {
      "image_quality_threshold": 40,
      "confidence_threshold": 70
    }
  }'
```

### Example 2: Full Processing with All Features

```bash
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "file",
      "file": "'"$(base64 -w 0 document.pdf)"'"
    },
    "processing_options": {
      "enable_ocr": true,
      "enable_enhancement": true,
      "enable_preprocessing": true,
      "return_format": "full"
    },
    "thresholds": {
      "image_quality_threshold": 60,
      "confidence_threshold": 80
    }
  }'
```

### Example 3: Test Different Formats

```bash
# Test PNG
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{"source": {"type": "file", "file": "'"$(base64 -w 0 image.png)"'"}}'

# Test PDF with specific page
curl -X POST "http://localhost:8000/api/v1/ocr?page_number=2" \
  -H "Content-Type: application/json" \
  -d '{"source": {"type": "file", "file": "'"$(base64 -w 0 document.pdf)"'"}}'

# Test TIFF with preprocessing disabled
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"type": "file", "file": "'"$(base64 -w 0 document.tiff)"'"},
    "processing_options": {"enable_preprocessing": false}
  }'
```

### Example 4: Python Client

```python
import requests
import base64
from pathlib import Path

def process_document(file_path, enable_enhancement=False):
    """Process any supported document format"""

    # Read and encode file
    with open(file_path, 'rb') as f:
        file_base64 = base64.b64encode(f.read()).decode('utf-8')

    # Prepare request
    request_data = {
        'source': {
            'type': 'file',
            'file': file_base64
        },
        'processing_options': {
            'enable_ocr': True,
            'enable_enhancement': enable_enhancement,
            'enable_preprocessing': True,
            'return_format': 'full'
        },
        'thresholds': {
            'image_quality_threshold': 60,
            'confidence_threshold': 80
        }
    }

    # Send request
    response = requests.post('http://localhost:8000/api/v1/ocr', json=request_data)
    result = response.json()

    # Process result
    if result['status'] == 'success':
        print(f"Format detected: {file_path.suffix.upper()}")
        print(f"Quality score: {result.get('quality_check', {}).get('score', 0):.1f}")
        print(f"Word count: {result.get('ocr_result', {}).get('word_count', 0)}")
        print(f"Confidence: {result['confidence_report']['final_confidence']:.1f}%")
        print(f"Routing: {result['confidence_report']['routing_decision']}")

    return result

# Test different formats
for file_path in Path('tests/documents').glob('*'):
    if file_path.suffix.lower() in ['.png', '.jpg', '.pdf', '.tiff']:
        print(f"\nProcessing {file_path.name}...")
        process_document(file_path)
```

## Performance Guidelines

### Processing Times

| Stage | Time | Notes |
|-------|------|-------|
| Format Detection | < 0.1s | Magic byte detection |
| Quality Check | < 1s | OpenCV analysis |
| Preprocessing | 1-3s | When needed |
| OCR Processing | 2-10s | Depends on document |
| LLM Enhancement | 20-30s | Optional, AI-powered |
| **Total (without LLM)** | 3-14s | Typical range |
| **Total (with LLM)** | 23-44s | Full pipeline |

### Optimization Tips

1. **Skip Enhancement**: For faster processing, set `enable_enhancement=false`
2. **Disable Preprocessing**: If document quality is good, set `enable_preprocessing=false`
3. **Lower Quality Threshold**: Reduce `image_quality_threshold` for poor quality documents
4. **Async Processing**: Use `async_processing=true` for large batches
5. **Minimal Format**: Use `return_format="minimal"` for reduced payload size

## Error Handling

### Common Errors

1. **Invalid Base64**
   - Error: "Invalid base64 file data"
   - Solution: Ensure proper base64 encoding without line breaks

2. **Unsupported Format**
   - Error: "Format XYZ is not supported"
   - Solution: Check supported formats list

3. **File Too Large**
   - Error: "File exceeds size limit"
   - Solution: Compress or resize images (max 10MB)

4. **Quality Too Low**
   - Response: Quality check fails, OCR skipped
   - Solution: Lower `image_quality_threshold` or improve image quality

## Testing

### Quick Test Script

```bash
# Save as test_api.sh
#!/bin/bash

# Test with local JPG
IMAGE_BASE64=$(base64 -w 0 tests/documents/scanned_document.jpg)

curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"type": "file", "file": "'"$IMAGE_BASE64"'"},
    "processing_options": {
      "enable_ocr": true,
      "enable_preprocessing": true,
      "return_format": "minimal"
    }
  }' | python3 -m json.tool
```

### Integration Testing

Run comprehensive tests:

```bash
# Test all pipeline configurations
pytest tests/integration/test_complete_pipeline.py -v

# Test with real documents
python tests/integration/test_complete_pipeline.py --api
```

## Monitoring

### Key Metrics

1. **Response Time**: Monitor P50, P95, P99 latencies
2. **Error Rate**: Track 4xx and 5xx errors
3. **Format Distribution**: Track usage by file format
4. **Preprocessing Impact**: Monitor quality improvements
5. **Routing Distribution**: Monitor pass vs manual review ratio

### Health Monitoring

- Endpoint: `GET /health`
- Check frequency: Every 30 seconds
- Alert threshold: 3 consecutive failures

## API Versioning

Current version: `v1`

Version is included in the URL path: `/api/v1/ocr`

Future versions will maintain backward compatibility or provide migration guides.

## Support

For issues or questions:
- GitHub Issues: [Project Repository]
- API Status: Check `/health` endpoint
- Logs: Available in Streamlit demo interface

## Changelog

### Version 1.1 (2025-09-22)
- Added support for 11 file formats (PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, PCX, ICO, PSD, PDF)
- Added preprocessing pipeline with OpenCV
- PDF page-by-page processing support
- Format validation endpoint
- Processing history (7-day retention)
- Batch processing endpoint (up to 20 files)

### Version 1.0 (2025-01-19)
- Initial release with unified OCR endpoint
- Quality gate implementation
- LLM enhancement support
- Dual threshold routing system
- Multiple response formats
- Async processing support