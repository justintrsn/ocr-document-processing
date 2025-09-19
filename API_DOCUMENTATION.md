# OCR Document Processing API Documentation

## Overview

The OCR Document Processing API provides a unified endpoint for document analysis with quality assessment, OCR extraction, and optional LLM enhancement. The system implements a dual-threshold routing system for automatic quality control.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. In production, implement API key or OAuth2 authentication.

## Endpoints

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
    "enable_enhancement": false,       // Default: false
    "return_format": "full"            // Options: "full", "minimal", "ocr_only"
  },
  "thresholds": {
    "image_quality_threshold": 60.0,   // Default: 60, Range: 0-100
    "confidence_threshold": 80.0       // Default: 80, Range: 0-100
  },
  "async_processing": false            // Default: false
}
```

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
  "detail": "Error message describing the issue"
}
```

Common error codes:
- `400` - Invalid request (bad base64, missing required fields)
- `422` - Validation error (invalid parameter values)
- `500` - Internal server error

### 2. Get Async Job Status

**Endpoint**: `GET /api/v1/ocr/job/{job_id}`

**Description**: Retrieves the status and results of an asynchronous OCR job.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | String | Yes | The job ID returned from async processing |

#### Response

```json
{
  "job_id": "job_xyz789ghi012",
  "status": "completed",  // Options: "pending", "processing", "completed", "failed"
  "progress_percentage": 100,
  "result": {
    // Full OCR response object when completed
  },
  "error": null
}
```

### 3. Health Check

**Endpoint**: `GET /health`

**Description**: Check API health status.

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2025-01-19T10:30:00Z"
}
```

## Processing Logic

### Quality Gate

1. **Quality Check**: Always performed first
2. **Gate Decision**: If quality score < `image_quality_threshold`, OCR is skipped
3. **Result**: Quality metrics are always included in response

### OCR Processing

1. **Conditional**: Only if quality check passes and `enable_ocr=true`
2. **Confidence Analysis**: Calculates word-level confidence distribution
3. **Result**: Extracted text with confidence metrics

### LLM Enhancement

1. **Optional**: Only if `enable_enhancement=true`
2. **Comprehensive**: Single LLM call for all improvements
3. **Corrections**: Spelling, grammar, punctuation, context
4. **Performance**: Typically 20-30 seconds

### Routing Decision

The system uses a dual-threshold system:

1. **Quality Check**: `image_quality_score >= image_quality_threshold`
2. **Confidence Check**: `final_confidence >= confidence_threshold`
3. **Final Confidence**: Calculated as weighted average:
   - Image Quality: 50%
   - OCR Confidence: 50%

**Routing Results**:
- `"pass"`: Both thresholds met, automatic processing
- `"requires_review"`: One or both thresholds not met, manual review needed

## Usage Examples

### Example 1: Quick OCR (No Enhancement)

```bash
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "file",
      "file": "'"$(base64 -w 0 document.jpg)"'"
    },
    "processing_options": {
      "enable_ocr": true,
      "enable_enhancement": false,
      "return_format": "ocr_only"
    },
    "thresholds": {
      "image_quality_threshold": 40,
      "confidence_threshold": 70
    }
  }'
```

### Example 2: Full Processing with Enhancement

```bash
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "obs_url",
      "obs_url": "obs://my-bucket/documents/scan.pdf"
    },
    "processing_options": {
      "enable_ocr": true,
      "enable_enhancement": true,
      "return_format": "full"
    },
    "thresholds": {
      "image_quality_threshold": 60,
      "confidence_threshold": 80
    }
  }'
```

### Example 3: Python Client

```python
import requests
import base64

# Read and encode image
with open('document.jpg', 'rb') as f:
    file_base64 = base64.b64encode(f.read()).decode('utf-8')

# Prepare request
request_data = {
    'source': {
        'type': 'file',
        'file': file_base64
    },
    'processing_options': {
        'enable_ocr': True,
        'enable_enhancement': True,
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
    print(f"Extracted text: {result['ocr_result']['raw_text']}")
    print(f"Confidence: {result['confidence_report']['final_confidence']}%")
    print(f"Routing: {result['confidence_report']['routing_decision']}")
```

## Performance Guidelines

### Processing Times

- **Quality Check**: < 1 second
- **OCR Processing**: 1-6 seconds (depends on document complexity)
- **LLM Enhancement**: 20-30 seconds
- **Total (with enhancement)**: 25-35 seconds
- **Total (without enhancement)**: 2-7 seconds

### Optimization Tips

1. **Skip Enhancement**: For faster processing, set `enable_enhancement=false`
2. **Lower Quality Threshold**: Reduce `image_quality_threshold` for poor quality documents
3. **Async Processing**: Use `async_processing=true` for large batches
4. **Minimal Format**: Use `return_format="minimal"` for reduced payload size

## Error Handling

### Common Errors

1. **Invalid Base64**
   - Error: "Invalid base64 file data"
   - Solution: Ensure proper base64 encoding without line breaks

2. **OBS Access Error**
   - Error: "Failed to access OBS URL"
   - Solution: Check bucket permissions and URL format

3. **Quality Too Low**
   - Response: Quality check fails, OCR skipped
   - Solution: Lower `image_quality_threshold` or improve image quality

4. **Timeout**
   - Error: "Processing timeout"
   - Solution: Use async processing for large documents

## Rate Limits

- Development: No limits
- Production: Implement rate limiting based on requirements
- Recommended: 10 requests per second per client

## Monitoring

### Key Metrics

1. **Response Time**: Monitor P50, P95, P99 latencies
2. **Error Rate**: Track 4xx and 5xx errors
3. **Routing Distribution**: Monitor pass vs manual review ratio
4. **Enhancement Usage**: Track LLM usage for cost optimization

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

### Version 1.0 (2025-01-19)
- Initial release with unified OCR endpoint
- Quality gate implementation
- LLM enhancement support
- Dual threshold routing system
- Multiple response formats
- Async processing support