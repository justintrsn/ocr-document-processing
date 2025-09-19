"""
OCR Test Suite

This package contains tests for the OCR service with two modes of operation:

1. test_ocr_base64.py - Tests using base64-encoded local files
   - Use case: Local development, testing without OBS access
   - API field: 'data' with base64 string

2. test_ocr_obs_url.py - Tests using OBS-hosted files with URLs
   - Use case: Production scenario, UI integration
   - API field: 'url' with signed/public URLs

Both modes are supported by the Huawei OCR smart-document-recognizer API.
"""