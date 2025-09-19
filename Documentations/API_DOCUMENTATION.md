# OCR Document Processing API Documentation

## Base URL
```
http://localhost:8000
```

## Health Check

### GET /health
Check API health status

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-18T10:00:00",
  "version": "1.0.0"
}
```

## Document Processing

### POST /documents/process
Process a document for OCR

**Request Body (Option 1 - File Upload):**
```
Content-Type: multipart/form-data
file: [binary file data]
```

**Request Body (Option 2 - OBS Key):**
```json
{
  "obs_key": "OCR/document.jpg"
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "status": "auto_processed",
  "confidence_score": 95.5,
  "message": "Document processed successfully with 95.50% confidence"
}
```

### GET /documents/{document_id}/status
Get processing status of a document

**Response:**
```json
{
  "document_id": "uuid",
  "status": "auto_processed",
  "created_at": "2025-01-18T10:00:00",
  "completed_at": "2025-01-18T10:00:05",
  "confidence_score": 95.5
}
```

### GET /documents/{document_id}/result
Get OCR results for a processed document

**Response:**
```json
{
  "document_id": "uuid",
  "status": "auto_processed",
  "confidence_score": 95.5,
  "extracted_text": "Document text content...",
  "ocr_data": {
    "result": [{
      "ocr_result": {...},
      "kv_result": {...},
      "table_result": {...},
      "layout_result": {...}
    }]
  },
  "created_at": "2025-01-18T10:00:00",
  "completed_at": "2025-01-18T10:00:05"
}
```

## OBS Integration

### GET /obs/list
List objects and folders in OBS bucket

**Query Parameters:**
- `prefix` (string, default: "OCR/"): Object prefix to filter
- `include_folders` (boolean, default: true): Include folder listing

**Response:**
```json
{
  "prefix": "OCR/",
  "folders": [
    "OCR/medical",
    "OCR/invoices",
    "OCR/contracts"
  ],
  "objects": [
    {
      "key": "OCR/document.jpg",
      "name": "document.jpg",
      "size": 285054,
      "size_mb": 0.27,
      "last_modified": "2025-01-18T10:00:00",
      "type": "jpg"
    }
  ],
  "total_objects": 15,
  "total_folders": 3
}
```

### GET /obs/metadata/{object_key}
Get metadata for a specific OBS object

**Path Parameters:**
- `object_key`: Full object key path (e.g., "OCR/medical/report.pdf")

**Response:**
```json
{
  "key": "OCR/medical/report.pdf",
  "size": 1048576,
  "content_type": "application/pdf",
  "last_modified": "2025-01-18T10:00:00",
  "etag": "abc123def456"
}
```

### POST /obs/process-batch
Process multiple documents from OBS in batch

**Request Body:**
```json
{
  "object_keys": [
    "OCR/document1.jpg",
    "OCR/document2.pdf",
    "OCR/medical/report.png"
  ],
  "options": {
    "kv": true,
    "table": true
  }
}
```

**Response:**
```json
{
  "summary": {
    "total": 3,
    "successful": 2,
    "failed": 0,
    "not_found": 1
  },
  "results": [
    {
      "key": "OCR/document1.jpg",
      "status": "success",
      "confidence_score": 95.5,
      "text_preview": "First 200 characters of extracted text...",
      "text_length": 1500,
      "processing_status": "auto_processed"
    },
    {
      "key": "OCR/document2.pdf",
      "status": "success",
      "confidence_score": 78.3,
      "text_preview": "First 200 characters...",
      "text_length": 2100,
      "processing_status": "manual_review"
    },
    {
      "key": "OCR/medical/report.png",
      "status": "not_found",
      "error": "Object not found: OCR/medical/report.png"
    }
  ]
}
```

## Queue Management

### GET /queue/manual-review
Get documents requiring manual review

**Response:**
```json
{
  "total": 2,
  "documents": [
    {
      "document_id": "uuid1",
      "filename": "document1.jpg",
      "confidence_score": 75.5,
      "created_at": "2025-01-18T10:00:00",
      "status": "manual_review"
    },
    {
      "document_id": "uuid2",
      "filename": "document2.pdf",
      "confidence_score": 78.3,
      "created_at": "2025-01-18T11:00:00",
      "status": "manual_review"
    }
  ]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid file format. Supported formats: JPG, JPEG, PNG, PDF"
}
```

### 404 Not Found
```json
{
  "detail": "Document not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error processing document: [error message]"
}
```

## CLI Usage

### Process Local File
```bash
python -m src.cli.main process --file /path/to/document.jpg
```

### Process OBS File
```bash
python -m src.cli.main process --obs-key OCR/document.jpg
```

## Python SDK Usage

### List OBS Objects
```python
from src.services.obs_service import OBSService

obs = OBSService()

# List all objects in OCR folder
objects = obs.list_objects(prefix="OCR/")

# List folders
folders = obs.list_folders(prefix="OCR/")

# List objects in subfolder
medical_docs = obs.list_objects(prefix="OCR/medical/")

obs.close()
```

### Process Document from OBS
```python
from src.services.obs_service import OBSService
from src.services.ocr_service import HuaweiOCRService

obs = OBSService()
ocr = HuaweiOCRService()

# Get signed URL
url = obs.get_signed_url("OCR/document.jpg", expires_in=300)

# Process with OCR
response = ocr.process_document(image_url=url)

# Extract results
text = ocr.extract_text_from_response(response)
confidence = ocr.get_average_confidence(response)

print(f"Confidence: {confidence*100:.2f}%")
print(f"Text: {text}")

obs.close()
```

### Batch Processing
```python
import asyncio
import aiohttp

async def process_batch(object_keys):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/obs/process-batch",
            json={"object_keys": object_keys}
        ) as response:
            return await response.json()

# Process multiple documents
keys = [
    "OCR/doc1.jpg",
    "OCR/doc2.pdf",
    "OCR/medical/report.png"
]

results = asyncio.run(process_batch(keys))
print(f"Processed {results['summary']['successful']} documents successfully")
```

## Environment Variables

Required in `.env` file:

```bash
# Huawei Cloud Credentials
HUAWEI_ACCESS_KEY=your_access_key
HUAWEI_SECRET_KEY=your_secret_key
HUAWEI_PROJECT_ID=your_project_id
HUAWEI_REGION=ap-southeast-3

# OBS Configuration
OBS_BUCKET_NAME=your-bucket-name
OBS_ENDPOINT=https://obs.ap-southeast-3.myhuaweicloud.com

# OCR Configuration
HUAWEI_OCR_ENDPOINT=https://ocr.ap-southeast-3.myhuaweicloud.com
MANUAL_REVIEW_THRESHOLD=80
```

## Rate Limits

- Single document processing: No limit
- Batch processing: Maximum 100 documents per request
- OBS listing: Maximum 1000 objects per request

## Notes

1. All documents should be stored under the `OCR/` prefix in OBS
2. Subfolders are supported (e.g., `OCR/medical/`, `OCR/invoices/`)
3. Signed URLs expire after the specified duration (default: 5 minutes)
4. Documents with confidence < 80% are marked for manual review
5. Maximum file size: 10MB (7MB recommended for optimal performance)