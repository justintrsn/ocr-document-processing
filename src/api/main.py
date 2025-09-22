"""
FastAPI application for OCR Document Processing System
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

from src.core.config import settings
from src.api.endpoints import documents, status, health, cost, ocr, batch, history, preprocessing

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting OCR Document Processing API...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.app_debug}")

    yield

    # Shutdown
    logger.info("Shutting down OCR Document Processing API...")


# Create FastAPI application
app = FastAPI(
    title="OCR Document Processing API",
    description="Document processing system with OCR, quality assessment, and LLM enhancement",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.app_debug
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else ["http://localhost:3000", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.app_debug else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include routers
app.include_router(ocr.router, tags=["OCR"])  # Main OCR processing endpoint
app.include_router(batch.router, tags=["Batch"])  # Batch processing endpoint
app.include_router(history.router, tags=["History"])  # History retrieval endpoint
app.include_router(preprocessing.router, tags=["Preprocessing"])  # Preprocessing endpoints
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(status.router, prefix="/documents", tags=["Status"])
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(cost.router, prefix="/cost", tags=["Cost"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "OCR Document Processing API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug
    )