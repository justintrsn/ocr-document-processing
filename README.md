# 🔍 OCR Document Processing System with AI Enhancement

An intelligent document processing system that combines Huawei OCR with DeepSeek V3 LLM for high-accuracy text extraction and enhancement.

## ✨ Features

- **🎯 Mandatory Quality Assessment**: Automatic image quality checks that gate OCR processing
- **📄 Huawei OCR Integration**: Enterprise-grade OCR with detailed confidence scoring
- **🤖 LLM Enhancement**: Comprehensive text improvement using DeepSeek V3 (single optimized call)
- **📊 Dual Threshold System**: Smart routing based on quality and confidence scores
- **⚡ Unified API**: Single endpoint with flexible processing options
- **🔄 Processing Modes**: Synchronous and asynchronous processing support
- **📈 Multiple Response Formats**: Full, minimal, or OCR-only responses
- **☁️ Cloud Storage**: Support for Huawei OBS (Object Storage Service)
- **🎨 Web Interface**: Interactive Streamlit demo with real-time logs
- **📚 REST API**: Full-featured FastAPI with auto-generated OpenAPI docs

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Huawei Cloud credentials (for OCR service)
- DeepSeek API key (for LLM enhancement)
- 4GB RAM minimum

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ocr-llm-project
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. **Run the demo**
```bash
./run_demo.sh
```

This will:
- Install all dependencies
- Start the API server on http://localhost:8000
- Launch Streamlit UI on http://localhost:8501

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start API server
python -m uvicorn src.api.main:app --reload

# In another terminal, start Streamlit
streamlit run streamlit_app.py
```

## 📖 Usage

### Web Interface (Streamlit)

1. Open http://localhost:8501
2. Configure processing settings in the sidebar:
   - Image quality threshold (default: 60)
   - Confidence threshold (default: 80)
   - Enable/disable OCR and LLM enhancement
   - Select response format
3. Upload a document or provide an OBS URL
4. Click "Process Document" and monitor real-time progress
5. View results, confidence scores, corrections, and logs

### Unified API Endpoint

Access API documentation at http://localhost:8000/docs

**Main endpoint:**
- `POST /api/v1/ocr` - Unified document processing endpoint

### Example API Usage

#### Basic OCR (No Enhancement)
```python
import requests
import base64

# Read and encode image
with open('document.jpg', 'rb') as f:
    file_base64 = base64.b64encode(f.read()).decode('utf-8')

# Send request
response = requests.post(
    'http://localhost:8000/api/v1/ocr',
    json={
        'source': {
            'type': 'file',
            'file': file_base64
        },
        'processing_options': {
            'enable_ocr': True,
            'enable_enhancement': False,
            'return_format': 'minimal'
        },
        'thresholds': {
            'image_quality_threshold': 60,
            'confidence_threshold': 80
        }
    }
)

result = response.json()
print(f"Text: {result.get('extracted_text')}")
print(f"Confidence: {result.get('confidence_score')}%")
print(f"Routing: {result.get('routing_decision')}")
```

#### Full Processing with Enhancement
```python
response = requests.post(
    'http://localhost:8000/api/v1/ocr',
    json={
        'source': {
            'type': 'obs_url',
            'obs_url': 'obs://bucket-name/path/to/document.jpg'
        },
        'processing_options': {
            'enable_ocr': True,
            'enable_enhancement': True,  # Single LLM call for all improvements
            'return_format': 'full'
        },
        'thresholds': {
            'image_quality_threshold': 60,
            'confidence_threshold': 80
        }
    }
)
```

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Document  │────▶│   Quality   │────▶│     OCR     │
│    Input    │     │Check (Gate) │     │  (Huawei)   │
└─────────────┘     └─────────────┘     └─────────────┘
                            │                     │
                      (if < threshold)            ▼
                            ▼              ┌─────────────┐
                      ┌─────────────┐      │     LLM     │
                      │  Skip OCR   │      │Enhancement  │
                      └─────────────┘      │ (Optional)  │
                                           └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │  Confidence │
                                          │   Scoring   │
                                          └─────────────┘
                                                  │
                                    ┌─────────────┴─────────────┐
                                    ▼                           ▼
                            ┌─────────────┐           ┌─────────────┐
                            │    Pass     │           │   Requires  │
                            │(Automatic)  │           │    Review   │
                            │   (≥80%)    │           │    (<80%)   │
                            └─────────────┘           └─────────────┘
```

## 🔧 Configuration

### Environment Variables

Key settings in `.env`:

```env
# Huawei OCR
HUAWEI_OCR_ENDPOINT=https://ocr.ap-southeast-3.myhuaweicloud.com
HUAWEI_PROJECT_ID=your_project_id
HUAWEI_AK=your_access_key
HUAWEI_SK=your_secret_key
HUAWEI_REGION=ap-southeast-3

# Huawei OBS (Optional)
OBS_ACCESS_KEY_ID=your_obs_access_key
OBS_SECRET_ACCESS_KEY=your_obs_secret_key
OBS_BUCKET_NAME=your_bucket_name
OBS_ENDPOINT=https://obs.ap-southeast-3.myhuaweicloud.com

# DeepSeek LLM
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
```

### Processing Configuration

#### Thresholds (Defaults)
- **Image Quality Threshold**: 60 (0-100) - Minimum quality to proceed with OCR
- **Confidence Threshold**: 80 (0-100) - Minimum confidence for automatic routing

#### Processing Options
- **enable_ocr**: Enable OCR extraction (default: true)
- **enable_enhancement**: Enable LLM enhancement (default: false)
- **return_format**: Response format - `full`, `minimal`, or `ocr_only`
- **async_processing**: Process asynchronously (default: false)

#### Routing Logic
- **Quality Gate**: Image quality < threshold → OCR skipped
- **Confidence Routing**:
  - Final confidence ≥ threshold → "pass" (automatic processing)
  - Final confidence < threshold → "requires_review"
- **Final Confidence**: 50% Image Quality + 50% OCR Confidence

## 📊 Performance

| Operation | Typical Time | Max Time |
|-----------|-------------|----------|
| Quality Check | < 1s | 2s |
| OCR Processing | 2-4s | 6s |
| LLM Enhancement | 20-25s | 30s |
| **Total (no enhancement)** | 3-5s | 8s |
| **Total (with enhancement)** | 25-30s | 35s |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/
pytest tests/performance/

# Test with coverage
pytest --cov=src tests/
```

### Using Postman

1. Import collection: `postman/OCR_API_Collection.postman_collection.json`
2. Import environment: `postman/OCR_API_Environment.postman_environment.json`
3. Set your test image in the `sample_base64` environment variable
4. Run the collection tests

## 📝 Project Structure

```
ocr-llm-project/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── main.py       # App initialization
│   │   └── endpoints/    # API endpoints
│   │       └── ocr.py    # Unified OCR endpoint
│   ├── models/           # Pydantic models
│   │   └── ocr_api.py    # Request/response models
│   ├── services/         # Business logic
│   │   ├── image_quality_service.py
│   │   ├── ocr_service.py
│   │   ├── llm_enhancement_service.py
│   │   ├── processing_orchestrator.py
│   │   └── response_builder.py
│   └── utils/            # Utilities
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── contract/         # API contract tests
│   ├── performance/      # Performance tests
│   └── documents/        # Test documents
├── postman/              # Postman collections
├── docs/                 # Additional documentation
├── streamlit_app.py      # Streamlit web UI
├── API_DOCUMENTATION.md  # Detailed API docs
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
└── run_demo.sh          # Demo launcher script
```

## 🚦 API Response Examples

### Full Response Format
```json
{
  "status": "success",
  "quality_check": {
    "performed": true,
    "passed": true,
    "score": 82.5,
    "metrics": {...}
  },
  "ocr_result": {
    "raw_text": "Extracted text...",
    "word_count": 150,
    "confidence_score": 94.5
  },
  "enhancement": {
    "performed": true,
    "enhanced_text": "Corrected text...",
    "corrections": [...]
  },
  "confidence_report": {
    "final_confidence": 88.5,
    "routing_decision": "pass",
    "routing_reason": "All thresholds met"
  },
  "metadata": {
    "document_id": "doc_abc123",
    "processing_time_ms": 25000
  }
}
```

### Minimal Response Format
```json
{
  "status": "success",
  "extracted_text": "Final text...",
  "routing_decision": "pass",
  "confidence_score": 88.5,
  "document_id": "doc_abc123"
}
```

## 🚀 Development Status

**Completed ✅**:
- Unified OCR API endpoint
- Mandatory quality assessment as OCR gate
- Huawei OCR integration with confidence analysis
- DeepSeek V3 LLM enhancement (single optimized call)
- Dual threshold routing system
- Multiple response formats
- Async processing support
- FastAPI REST endpoints
- Streamlit web interface with logs
- Comprehensive test suite
- API documentation
- Postman collection

**Future Enhancements**:
- Docker containerization
- Kubernetes deployment manifests
- Rate limiting and authentication
- Batch processing endpoints
- WebSocket support for real-time updates
- Multi-language OCR support

## 📄 License

This is a proof-of-concept implementation for document processing with AI enhancement.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a pull request

## 📧 Support

- **API Documentation**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Interactive API Docs**: http://localhost:8000/docs
- **Logs**: Available in Streamlit demo (Logs tab)
- **Issues**: Please open an issue on GitHub

## 🙏 Acknowledgments

- Huawei Cloud for OCR services
- DeepSeek for LLM capabilities
- FastAPI for the excellent web framework
- Streamlit for the demo interface