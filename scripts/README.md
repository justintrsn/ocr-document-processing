# Scripts Directory

This directory contains utility scripts for running and testing the OCR API system.

## Available Scripts

### 1. `run_demo.sh`
Starts both the API server and Streamlit UI in a single terminal with proper cleanup on exit.

```bash
./scripts/run_demo.sh
```

### 2. `test_ocr_local.sh`
Tests the OCR API endpoint with a local image file (base64 encoded).

```bash
./scripts/test_ocr_local.sh
```

### 3. `test_ocr_obs.sh`
Tests the OCR API endpoint with images stored in Huawei OBS.

```bash
./scripts/test_ocr_obs.sh
```

## Usage Notes

- All scripts assume the virtual environment is at `.venv/`
- The API runs on port 8000 by default
- Streamlit runs on port 8501 by default
- Make sure to activate the virtual environment or the scripts will handle it automatically

## Running Services Separately

If you need to run services in separate terminals:

**Terminal 1 (API):**
```bash
source .venv/bin/activate
python -m src.api.main
```

**Terminal 2 (Streamlit):**
```bash
source .venv/bin/activate
streamlit run streamlit_app.py
```