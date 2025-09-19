#!/bin/bash

# Base64 encode the image
IMAGE_BASE64=$(base64 -w 0 tests/documents/scanned_document.jpg)

# Create JSON request
cat << JSON > /tmp/ocr_request.json
{
  "source": {
    "type": "file",
    "file": "${IMAGE_BASE64}"
  },
  "processing_options": {
    "enable_quality_check": true,
    "enable_ocr": true,
    "enable_enhancement": false,
    "return_format": "minimal"
  },
  "thresholds": {
    "image_quality_threshold": 30,
    "confidence_threshold": 80
  },
  "async_processing": false
}
JSON

# Send request to OCR endpoint
echo "Testing OCR with local file..."
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d @/tmp/ocr_request.json \
  | python3 -m json.tool
