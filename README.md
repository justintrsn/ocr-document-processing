# 🔍 OCR Document Processing System with AI Enhancement

An intelligent document processing system that combines Huawei OCR with DeepSeek V3.1 LLM for high-accuracy text extraction and enhancement.

## ✨ Features

- **🎯 Quality Gates**: Automatic image quality assessment to prevent unnecessary processing
- **📄 Huawei OCR Integration**: Enterprise-grade OCR with confidence scoring
- **🤖 LLM Enhancement**: Grammar correction, context analysis, and structure validation using DeepSeek V3.1
- **📊 Confidence Scoring**: Multi-layer validation with weighted scoring (Image 20%, OCR 30%, Grammar 20%, Context 20%, Structure 10%)
- **🚦 Smart Routing**: Automatic processing for high-confidence documents, manual review for others
- **☁️ Cloud Storage**: Support for Huawei OBS (Object Storage Service)
- **🎨 Web Interface**: Interactive Streamlit demo with real-time processing status
- **📚 REST API**: Full-featured FastAPI with OpenAPI documentation

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Huawei Cloud credentials (OCR API access)
- Huawei ModelArts MAAS API key (for DeepSeek V3.1)

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
python -m src.api.main

# In another terminal, start Streamlit
streamlit run streamlit_app.py
```

## 📖 Usage

### Web Interface (Streamlit)

1. Open http://localhost:8501
2. Configure processing settings in the sidebar:
   - Image quality threshold (default: 30%)
   - Confidence threshold (default: 80%)
   - Enable/disable LLM enhancements
3. Upload a document or provide an OBS URL
4. Click "Process Document" and monitor real-time progress
5. View results, confidence scores, and corrections

### API Endpoints

Access API documentation at http://localhost:8000/docs

**Key endpoints:**

- `POST /documents/process` - Submit document for processing
- `GET /documents/{id}/status` - Check processing status
- `GET /documents/{id}/result` - Get processing results
- `GET /documents/{id}/confidence` - Get confidence breakdown
- `GET /queue/manual-review` - View manual review queue
- `POST /cost/estimate` - Estimate processing costs

### Example API Usage

```python
import requests

# Process a document
response = requests.post(
    "http://localhost:8000/documents/process",
    files={"file": open("document.jpg", "rb")},
    data={
        "quality_threshold": 30,
        "confidence_threshold": 80,
        "enable_grammar": True,
        "enable_context": False
    }
)

document_id = response.json()["document_id"]

# Check status
status = requests.get(f"http://localhost:8000/documents/{document_id}/status")
print(status.json())

# Get results
result = requests.get(f"http://localhost:8000/documents/{document_id}/result")
print(result.json()["extracted_text"])
```

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Document  │────▶│Quality Gate  │────▶│    OCR      │
│   Upload    │     │  (30% min)   │     │  (Huawei)   │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                     │
                            ▼                     ▼
                    ┌──────────────┐     ┌─────────────┐
                    │     SKIP     │     │LLM Enhance  │
                    │(if too poor) │     │ (DeepSeek)  │
                    └──────────────┘     └─────────────┘
                                                 │
                                                 ▼
                                        ┌─────────────┐
                                        │  Confidence │
                                        │   Scoring   │
                                        └─────────────┘
                                                 │
                                    ┌────────────┴────────────┐
                                    ▼                         ▼
                            ┌─────────────┐          ┌─────────────┐
                            │  Automatic  │          │   Manual    │
                            │ Processing  │          │   Review    │
                            │   (≥80%)    │          │   (<80%)    │
                            └─────────────┘          └─────────────┘
```

## 🔧 Configuration

### Environment Variables

Key settings in `.env`:

```env
# Huawei OCR
HUAWEI_OCR_ENDPOINT=https://ocr.ap-southeast-3.myhuaweicloud.com
HUAWEI_ACCESS_KEY=your_access_key
HUAWEI_SECRET_KEY=your_secret_key
HUAWEI_PROJECT_ID=your_project_id

# LLM (DeepSeek V3.1)
MAAS_API_KEY=your_api_key
MAAS_BASE_URL=https://api.modelarts-maas.com/v1
MAAS_MODEL_NAME=deepseek-v3.1

# Processing Thresholds
PROCESSING_TIMEOUT=180
MANUAL_REVIEW_THRESHOLD=80
```

### Processing Configuration

- **Quality Threshold**: Minimum image quality to proceed (0-100)
- **Confidence Threshold**: Minimum confidence for automatic processing (0-100)
- **Enhancement Types**:
  - `grammar`: Spelling and grammar correction
  - `context`: Document context analysis
  - `structure`: Document structure validation
  - `complete`: All enhancements

## 📊 Performance

- **Image Quality Check**: < 1 second
- **OCR Processing**: < 6 seconds
- **LLM Enhancement**: 20-30 seconds per type
- **Total Timeout**: 3 minutes

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Test orchestrator
python tests/integration/test_orchestrator.py
```

## 📝 Project Structure

```
ocr-llm-project/
├── src/
│   ├── api/              # FastAPI endpoints
│   ├── core/             # Configuration
│   ├── models/           # Data models
│   └── services/         # Business logic
│       ├── image_quality_service.py
│       ├── ocr_service.py
│       ├── llm_enhancement_service.py
│       └── processing_orchestrator.py
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── documents/        # Test documents
├── streamlit_app.py      # Web UI
├── run_demo.sh          # Demo launcher
└── requirements.txt     # Dependencies
```

## 🚧 Development Status

**Completed (75%)**:
- ✅ Image quality assessment with configurable thresholds
- ✅ Huawei OCR integration with confidence analysis
- ✅ DeepSeek V3.1 LLM enhancement
- ✅ Processing orchestrator with quality gates
- ✅ FastAPI REST endpoints
- ✅ Streamlit web interface
- ✅ Cost estimation
- ✅ Testing framework

**Remaining**:
- ⏳ CLI tools for batch processing
- ⏳ Docker containerization
- ⏳ Production deployment guide
- ⏳ Performance optimization

## 📄 License

This is a proof-of-concept implementation for document processing with AI enhancement.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## 📧 Support

For issues or questions, please open an issue on GitHub.