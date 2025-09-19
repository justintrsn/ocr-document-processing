#!/bin/bash

# Create JSON request for OBS
cat << JSON > /tmp/ocr_obs_request.json
{
  "source": {
    "type": "obs_url",
    "obs_url": "obs://sample-data-bucket/OCR/scanned_document.jpg"
  },
  "processing_options": {
    "enable_quality_check": true,
    "enable_ocr": true,
    "enable_enhancement": false,
    "return_format": "full"
  },
  "thresholds": {
    "image_quality_threshold": 30,
    "confidence_threshold": 80
  },
  "async_processing": false
}
JSON

# Send request to OCR endpoint
echo "Testing OCR with OBS URL..."
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d @/tmp/ocr_obs_request.json \
  | python3 -m json.tool
