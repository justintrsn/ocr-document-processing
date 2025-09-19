# Test Documents Directory

This directory contains test documents for OCR and image quality assessment tests.

## Current Documents

- `scanned_document.jpg` - Default test document (medical certificate)

## Adding New Test Documents

To add new test documents for testing:

1. Place your test document in this directory (e.g., `scanned_document2.jpg`)

2. Update the test configuration in `/tests/test_config.yaml`:
   ```yaml
   documents:
     test_files:
       - scanned_document.jpg
       - scanned_document2.jpg  # Add your new document here
   ```

3. For OBS testing, also add the OBS key:
   ```yaml
   obs:
     test_keys:
       - "OCR/scanned_document.jpg"
       - "OCR/scanned_document2.jpg"  # Add OBS key here
   ```

## Configuration Options

### Test All Documents
By default, tests run on all configured documents. To test only the first document:
```yaml
documents:
  test_all: false  # Only test first document
```

### Environment Variable Override
You can override the test documents via environment variable:
```bash
TEST_DOCUMENTS="doc1.jpg,doc2.png" pytest tests/image_quality/
```

## Test Types

### Single Document Tests
- Basic quality assessment
- OCR processing
- Enhancement recommendations

### Batch Processing Tests
- Queue routing based on confidence scores
- Parallel processing simulation
- Quality distribution analysis
- Batch size limit testing

## Document Requirements

- **Supported formats**: JPG, PNG, PDF, TIFF
- **Maximum size**: 10MB (optimal: <7MB)
- **Minimum resolution**: 150 DPI (optimal: 300+ DPI)
- **Languages**: English, Chinese

## Example Test Output

When multiple documents are configured, batch tests will show:

```
📊 Batch Assessment Results:
  - scanned_document.jpg: 82.1 (excellent)
  - medical_report.pdf: 65.3 (good)
  - invoice.png: 45.2 (fair)

📋 Queue Routing (threshold=80.0):
  Automatic processing: ['scanned_document.jpg']
  Manual review (high priority): ['invoice.png']
  Manual review (medium priority): ['medical_report.pdf']
  Manual review (low priority): []
```

This helps test the queue functionality and ensure documents are properly routed based on their quality scores.