# Makefile for OCR Document Processing System

.PHONY: help install install-dev test format lint type-check clean run run-api run-ui docker-build docker-run

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install development dependencies"
	@echo "  test          - Run tests"
	@echo "  format        - Format code with black and isort"
	@echo "  lint          - Run linting checks"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  clean         - Clean cache and temporary files"
	@echo "  run           - Run both API and Streamlit"
	@echo "  run-api       - Run API server only"
	@echo "  run-ui        - Run Streamlit UI only"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"

# Installation
install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

# Code Quality
format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/
	pylint src/

type-check:
	mypy src/

# Cleaning
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info

# Running Services
run:
	./scripts/run_demo.sh

run-api:
	python -m src.api.main

run-ui:
	streamlit run streamlit_app.py

# Docker
docker-build:
	docker build -t ocr-api:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env ocr-api:latest

# Development helpers
dev-setup: install-dev
	@echo "Development environment ready!"

check: format lint type-check test
	@echo "All checks passed!"