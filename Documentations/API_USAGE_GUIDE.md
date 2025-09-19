# OCR Document Processing API - Usage Guide

## Base URL
```
http://localhost:8000
```

## Authentication
Currently, no authentication is required for the API endpoints.

## API Endpoints

### 1. Health Check
Check if the API server is running.

**Endpoint:** `GET /health`

**Example Request:**
```bash
curl -X GET http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-19T10:30:45.123456"
}
```

---

### 2. Process Document
Submit a document for OCR processing with optional LLM enhancement.

**Endpoint:** `POST /documents/process`

**Methods:**
- **Option 1:** Upload a file
- **Option 2:** Provide an OBS URL

#### Option 1: File Upload

**Request:**
```bash
curl -X POST http://localhost:8000/documents/process \
  -F "file=@/path/to/document.jpg" \
  -F "quality_threshold=30" \
  -F "confidence_threshold=80" \
  -F "enable_context=true"
```

**Form Parameters:**
- `file` (required): The document file (JPG, JPEG, PNG, PDF)
- `quality_threshold` (optional, default=30): Minimum image quality score (0-100)
- `confidence_threshold` (optional, default=80): Minimum confidence for automatic processing (0-100)
- `enable_context` (optional, default=false): Enable LLM enhancement

#### Option 2: OBS URL

**Request:**
```bash
curl -X POST http://localhost:8000/documents/process \
  -F "obs_url=obs://bucket-name/document.jpg" \
  -F "quality_threshold=30" \
  -F "confidence_threshold=80" \
  -F "enable_context=true"
```

**Response:**
```json
{
  "document_id": "doc_abc123def456",
  "status": "processing",
  "message": "Document submitted for processing"
}
```

---

### 3. Check Processing Status
Get the current status of document processing.

**Endpoint:** `GET /documents/{document_id}/status`

**Example Request:**
```bash
curl -X GET http://localhost:8000/documents/doc_abc123def456/status
```

**Response:**
```json
{
  "document_id": "doc_abc123def456",
  "status": "completed",
  "progress": 100,
  "message": "Processing completed successfully"
}
```

**Status Values:**
- `pending`: Document queued for processing
- `processing`: Currently being processed
- `completed`: Successfully processed
- `manual_review`: Requires manual review (confidence below threshold)
- `failed`: Processing failed

---

### 4. Get Processing Results
Retrieve the complete processing results.

**Endpoint:** `GET /documents/{document_id}/result`

**Example Request:**
```bash
curl -X GET http://localhost:8000/documents/doc_abc123def456/result
```

**Response:**
```json
{
  "document_id": "doc_abc123def456",
  "status": "completed",
  "confidence_report": {
    "image_quality_score": 82.1,
    "ocr_confidence_score": 97.4,
    "final_confidence": 89.75,
    "routing_decision": "automatic",
    "priority_level": "low",
    "issues_detected": []
  },
  "extracted_text": "Original OCR extracted text...",
  "enhanced_text": "LLM enhanced and corrected text...",
  "corrections_made": [
    {
      "original": "teh",
      "corrected": "the",
      "confidence": 0.95,
      "type": "spelling"
    }
  ],
  "processing_metrics": {
    "quality_check_time": 2.87,
    "ocr_processing_time": 2.95,
    "llm_enhancement_time": {"combined": 25.3},
    "total_processing_time": 31.12,
    "words_extracted": 97,
    "corrections_applied": 4,
    "enhancements_applied": ["context"]
  },
  "word_count": 97
}
```

---

### 5. Get Confidence Details
Get detailed confidence scoring breakdown.

**Endpoint:** `GET /documents/{document_id}/confidence`

**Example Request:**
```bash
curl -X GET http://localhost:8000/documents/doc_abc123def456/confidence
```

**Response:**
```json
{
  "document_id": "doc_abc123def456",
  "confidence_scores": {
    "image_quality": 82.1,
    "ocr_confidence": 97.4,
    "final": 89.75
  },
  "routing": {
    "decision": "automatic",
    "reason": "Confidence score 89.75% exceeds threshold of 80%",
    "priority": "low"
  },
  "quality_issues": [],
  "recommendations": []
}
```

---

### 6. Manual Review Queue
Get documents pending manual review.

**Endpoint:** `GET /queue/manual-review`

**Query Parameters:**
- `priority` (optional): Filter by priority (high, medium, low)
- `limit` (optional, default=10): Maximum number of documents
- `offset` (optional, default=0): Pagination offset

**Example Request:**
```bash
curl -X GET "http://localhost:8000/queue/manual-review?priority=high&limit=5"
```

**Response:**
```json
{
  "documents": [
    {
      "document_id": "doc_xyz789",
      "submitted_at": "2025-01-19T10:30:00",
      "confidence_score": 65.3,
      "priority": "high",
      "issues": ["Low image quality", "Multiple low-confidence regions"]
    }
  ],
  "total": 1,
  "limit": 5,
  "offset": 0
}
```

---

### 7. Queue Statistics
Get overall queue statistics.

**Endpoint:** `GET /queue/stats`

**Example Request:**
```bash
curl -X GET http://localhost:8000/queue/stats
```

**Response:**
```json
{
  "total_documents": 150,
  "completed": 120,
  "manual_review": 25,
  "failed": 5,
  "processing": 0,
  "priority_distribution": {
    "high": 5,
    "medium": 10,
    "low": 10
  },
  "average_processing_time": 28.5,
  "success_rate": 80.0
}
```

---

### 8. Cost Estimation
Estimate processing costs before submitting documents.

**Endpoint:** `POST /cost/estimate`

**Request Body:**
```json
{
  "document_size_mb": 2.0,
  "enhancement_types": ["context"],
  "num_documents": 10
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/cost/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "document_size_mb": 2.0,
    "enhancement_types": ["context"],
    "num_documents": 10
  }'
```

**Response:**
```json
{
  "per_document": {
    "estimated_ocr_cost": 0.02,
    "estimated_llm_tokens": 50000,
    "estimated_llm_cost": 0.10,
    "estimated_total_cost": 0.12
  },
  "total": {
    "estimated_ocr_cost": 0.20,
    "estimated_llm_cost": 1.00,
    "estimated_total_cost": 1.20
  },
  "processing_time": {
    "per_document_seconds": 31.5,
    "total_seconds": 315
  }
}
```

---

## Postman Collection

### Setting Up Postman

1. **Import the Collection**
   - Open Postman
   - Click "Import" → "Raw text"
   - Paste the collection JSON below

2. **Set Environment Variables**
   - Create a new environment
   - Add variable: `base_url` = `http://localhost:8000`
   - Add variable: `document_id` = (will be set by scripts)

### Postman Collection JSON

```json
{
  "info": {
    "name": "OCR Document Processing API",
    "description": "API for OCR processing with LLM enhancement",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/health",
          "host": ["{{base_url}}"],
          "path": ["health"]
        }
      }
    },
    {
      "name": "Process Document (File Upload)",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "if (pm.response.code === 200) {",
              "    const response = pm.response.json();",
              "    pm.environment.set('document_id', response.document_id);",
              "    console.log('Document ID saved: ' + response.document_id);",
              "}"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "file",
              "type": "file",
              "src": "/path/to/your/document.jpg"
            },
            {
              "key": "quality_threshold",
              "value": "30",
              "type": "text"
            },
            {
              "key": "confidence_threshold",
              "value": "80",
              "type": "text"
            },
            {
              "key": "enable_context",
              "value": "true",
              "type": "text"
            }
          ]
        },
        "url": {
          "raw": "{{base_url}}/documents/process",
          "host": ["{{base_url}}"],
          "path": ["documents", "process"]
        }
      }
    },
    {
      "name": "Process Document (OBS URL)",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "if (pm.response.code === 200) {",
              "    const response = pm.response.json();",
              "    pm.environment.set('document_id', response.document_id);",
              "}"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "obs_url",
              "value": "obs://your-bucket/document.jpg",
              "type": "text"
            },
            {
              "key": "quality_threshold",
              "value": "30",
              "type": "text"
            },
            {
              "key": "confidence_threshold",
              "value": "80",
              "type": "text"
            },
            {
              "key": "enable_context",
              "value": "true",
              "type": "text"
            }
          ]
        },
        "url": {
          "raw": "{{base_url}}/documents/process",
          "host": ["{{base_url}}"],
          "path": ["documents", "process"]
        }
      }
    },
    {
      "name": "Check Status",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/documents/{{document_id}}/status",
          "host": ["{{base_url}}"],
          "path": ["documents", "{{document_id}}", "status"]
        }
      }
    },
    {
      "name": "Get Results",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/documents/{{document_id}}/result",
          "host": ["{{base_url}}"],
          "path": ["documents", "{{document_id}}", "result"]
        }
      }
    },
    {
      "name": "Get Confidence Details",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/documents/{{document_id}}/confidence",
          "host": ["{{base_url}}"],
          "path": ["documents", "{{document_id}}", "confidence"]
        }
      }
    },
    {
      "name": "Manual Review Queue",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/queue/manual-review?priority=high&limit=10",
          "host": ["{{base_url}}"],
          "path": ["queue", "manual-review"],
          "query": [
            {
              "key": "priority",
              "value": "high"
            },
            {
              "key": "limit",
              "value": "10"
            }
          ]
        }
      }
    },
    {
      "name": "Queue Statistics",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/queue/stats",
          "host": ["{{base_url}}"],
          "path": ["queue", "stats"]
        }
      }
    },
    {
      "name": "Cost Estimation",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"document_size_mb\": 2.0,\n  \"enhancement_types\": [\"context\"],\n  \"num_documents\": 10\n}"
        },
        "url": {
          "raw": "{{base_url}}/cost/estimate",
          "host": ["{{base_url}}"],
          "path": ["cost", "estimate"]
        }
      }
    }
  ]
}
```

---

## Testing Workflow

### 1. Basic OCR Processing (No Enhancement)
```bash
curl -X POST http://localhost:8000/documents/process \
  -F "file=@sample.jpg" \
  -F "enable_context=false"
```

### 2. OCR with LLM Enhancement
```bash
curl -X POST http://localhost:8000/documents/process \
  -F "file=@sample.jpg" \
  -F "enable_context=true"
```

### 3. Complete Processing Flow
```bash
# 1. Submit document
RESPONSE=$(curl -s -X POST http://localhost:8000/documents/process \
  -F "file=@sample.jpg" \
  -F "enable_context=true")

# 2. Extract document ID
DOC_ID=$(echo $RESPONSE | jq -r '.document_id')

# 3. Wait and check status
sleep 5
curl -X GET http://localhost:8000/documents/$DOC_ID/status

# 4. Get results
curl -X GET http://localhost:8000/documents/$DOC_ID/result | jq '.'
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 404 | Document not found |
| 413 | File too large (>10MB) |
| 422 | Unprocessable Entity (validation error) |
| 500 | Internal Server Error |

---

## Rate Limits

- Maximum file size: 10MB
- Optimal file size: <7MB
- Processing timeout: 3 minutes
- Concurrent requests: 10 (configurable)

---

## Best Practices

1. **Image Quality**
   - Use high-resolution images (300+ DPI)
   - Ensure good lighting and contrast
   - Avoid skewed or rotated documents

2. **Performance**
   - Keep files under 7MB for optimal processing
   - Enable LLM enhancement only when needed
   - Use batch processing for multiple documents

3. **Error Handling**
   - Always check the status endpoint before retrieving results
   - Implement retry logic for failed requests
   - Handle timeout scenarios (3-minute limit)

4. **Cost Optimization**
   - Use cost estimation endpoint before bulk processing
   - Disable LLM enhancement for simple documents
   - Process documents in batches during off-peak hours