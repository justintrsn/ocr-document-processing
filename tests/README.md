# OCR Document Processing Tests

## Test Structure

```
tests/
├── ocr/                           # OCR service tests
│   ├── scanned_document.jpg      # Test image file
│   ├── fixtures.py               # Shared test data and constants
│   ├── conftest.py               # Pytest fixtures
│   ├── test_ocr_base64.py       # Tests for base64 mode (local files)
│   ├── test_ocr_obs_url.py      # Tests for URL mode (OBS files)
│   ├── test_ocr_combined.py     # Tests showing both modes work
│   └── test_local_image.py      # Quick local tests with test image
├── integration/                   # Integration tests
│   └── test_obs_integration.py  # Real OBS service integration
└── unit/                         # Unit tests (future)
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test categories
```bash
# Unit tests only (fast)
pytest -m "not integration"

# Integration tests only
pytest -m integration

# OCR tests only
pytest tests/ocr/

# OBS integration tests
pytest tests/integration/
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html
```

## Test Modes

### 1. Base64 Mode (Local Files)
- **File**: `test_ocr_base64.py`
- **Purpose**: Test OCR with local files converted to base64
- **API Field**: `data`
- **Use Case**: Development, testing without OBS

### 2. URL Mode (OBS Files)
- **File**: `test_ocr_obs_url.py`
- **Purpose**: Test OCR with files hosted on OBS
- **API Field**: `url`
- **Use Case**: Production, UI integration

## Test Data

### Test Image
- **Location**: `tests/ocr/scanned_document.jpg`
- **Content**: Medical certificate sample
- **Size**: ~278KB
- **OBS Mirror**: `OCR/scanned_document.jpg` in bucket

### Fixtures
- **File**: `tests/ocr/fixtures.py`
- **Contains**:
  - Test image paths
  - Sample OCR responses
  - Test configurations
  - Expected results

### Shared Fixtures
- **File**: `tests/ocr/conftest.py`
- **Provides**:
  - Mock OCR service
  - Mock OBS service
  - Sample responses
  - Test data loaders

## Quick Test Commands

```bash
# Test with local image only
pytest tests/ocr/test_local_image.py -v

# Test both OCR modes
pytest tests/ocr/test_ocr_combined.py -v

# Test OBS operations
pytest tests/ocr/test_ocr_obs_url.py -v

# Run all OCR tests
pytest tests/ocr/ -v

# Skip slow tests
pytest -m "not slow" -v
```

## Environment Variables for Testing

For integration tests with real services:
```bash
export HUAWEI_ACCESS_KEY=your_access_key
export HUAWEI_SECRET_KEY=your_secret_key
export HUAWEI_PROJECT_ID=your_project_id
```

## Test Coverage Goals

- Unit Tests: > 80% coverage
- Integration Tests: Cover all API endpoints
- OCR Service: Both base64 and URL modes
- OBS Service: All CRUD operations

## Notes

1. The test image (`scanned_document.jpg`) is stored locally in `tests/ocr/` for quick testing
2. The same image should be uploaded to OBS at `OCR/scanned_document.jpg` for URL mode tests
3. Integration tests are marked with `@pytest.mark.integration` and can be skipped for faster testing
4. Mock services are used by default; real services require environment variables