# Huawei Cloud OBS Integration Guide

## Overview
This document explains how to use the OCR Document Processing System with Huawei Cloud Object Storage Service (OBS).

## Configuration

Add the following to your `.env` file:

```bash
# OBS Configuration
OBS_BUCKET_NAME=your-bucket-name
OBS_ENDPOINT=https://obs.ap-southeast-3.myhuaweicloud.com
```

## Usage

### 1. CLI Tool

Process documents stored in OBS:

```bash
# Process a document from OBS
python -m src.cli.main process --obs-key OCR/scanned_document.jpg

# Process a local file
python -m src.cli.main process --file /path/to/document.jpg
```

### 2. API Endpoints

#### Process Document from OBS

```bash
# Using curl
curl -X POST "http://localhost:8000/documents/process" \
  -H "Content-Type: application/json" \
  -d '{"obs_key": "OCR/scanned_document.jpg"}'

# Using Python requests
import requests

response = requests.post(
    "http://localhost:8000/documents/process",
    json={"obs_key": "OCR/scanned_document.jpg"}
)
print(response.json())
```

#### Process Uploaded Document

```bash
# Using curl
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@/path/to/document.jpg"
```

### 3. Python SDK

```python
from src.services.obs_service import OBSService
from src.services.ocr_service import HuaweiOCRService

# Initialize services
obs_service = OBSService()
ocr_service = HuaweiOCRService()

# Option 1: Process from OBS using signed URL
object_key = "OCR/scanned_document.jpg"
signed_url = obs_service.get_signed_url(object_key, expires_in=300)
ocr_response = ocr_service.process_document(image_url=signed_url)

# Option 2: Upload local file to OBS first
from pathlib import Path
local_file = Path("document.jpg")
obs_service.upload_file(local_file, "OCR/new_document.jpg")

# Option 3: Process local file directly
ocr_response = ocr_service.process_document(local_file)

# Extract results
text = ocr_service.extract_text_from_response(ocr_response)
confidence = ocr_service.get_average_confidence(ocr_response)
print(f"Confidence: {confidence*100:.2f}%")
print(f"Text: {text}")
```

## OBS Service Methods

### `OBSService` Class

- **`upload_file(local_path, object_key)`**: Upload a file to OBS
- **`get_signed_url(object_key, expires_in)`**: Generate a signed URL for temporary access
- **`get_public_url(object_key)`**: Get public URL (if bucket allows public access)
- **`check_object_exists(object_key)`**: Check if an object exists in OBS
- **`delete_object(object_key)`**: Delete an object from OBS

### Example: Batch Processing

```python
from src.services.obs_service import OBSService
from src.services.ocr_service import HuaweiOCRService

obs_service = OBSService()
ocr_service = HuaweiOCRService()

# Process multiple documents from OBS
document_keys = [
    "OCR/document1.jpg",
    "OCR/document2.pdf",
    "OCR/document3.png"
]

results = []
for key in document_keys:
    if obs_service.check_object_exists(key):
        url = obs_service.get_signed_url(key)
        response = ocr_service.process_document(image_url=url)
        results.append({
            "key": key,
            "text": ocr_service.extract_text_from_response(response),
            "confidence": ocr_service.get_average_confidence(response)
        })

# Clean up
obs_service.close()
```

## Testing

### Test OBS Integration

```bash
# Test OCR with OBS-hosted image
python test_obs_ocr.py

# Test with specific object key
python test_obs_ocr.py --key OCR/your_document.jpg
```

### Test URLs

```bash
# Test with URL-based OCR
python test_ocr_url.py

# Start local image server for testing
python serve_image.py
```

## Security Best Practices

1. **Use Signed URLs**: Always use signed URLs with short expiration times (5-10 minutes)
2. **Validate Object Keys**: Ensure object keys follow your naming convention
3. **Access Control**: Configure bucket policies to restrict access
4. **Encryption**: Enable server-side encryption for sensitive documents
5. **Audit Logging**: Enable OBS access logging for compliance

## Troubleshooting

### Common Issues

1. **"Object not found in OBS"**
   - Verify the object key is correct
   - Check bucket name in configuration
   - Ensure the object exists: `obs_service.check_object_exists(key)`

2. **"Failed to generate signed URL"**
   - Verify OBS credentials (AK/SK)
   - Check OBS endpoint configuration
   - Ensure bucket exists and is accessible

3. **"OCR API error: 400"**
   - Ensure the image format is supported (JPG, PNG, PDF)
   - Check file size limits (< 10MB after base64 encoding)
   - Verify the URL is accessible from Huawei Cloud

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set in .env
LOG_LEVEL=DEBUG
```

## Performance Tips

1. **Batch Processing**: Process multiple documents in parallel
2. **Caching**: Cache signed URLs for repeated access (within expiration time)
3. **Compression**: Compress images before upload to reduce transfer time
4. **Regional Deployment**: Deploy in the same region as your OBS bucket

## API Response Format

```json
{
  "document_id": "uuid",
  "status": "auto_processed",
  "confidence_score": 95.5,
  "message": "Document processed successfully",
  "source": "obs",
  "obs_key": "OCR/document.jpg"
}
```

## Support

For issues or questions:
- Check the logs in `./data/logs/`
- Review the test scripts for examples
- Ensure all environment variables are configured correctly