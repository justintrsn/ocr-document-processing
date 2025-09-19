"""Application configuration module."""
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class HuaweiConfig(BaseSettings):
    """Huawei OCR API configuration."""
    ocr_endpoint: str = Field(default="https://ocr.cn-north-4.myhuaweicloud.com", env="HUAWEI_OCR_ENDPOINT")
    access_key: str = Field(..., env="HUAWEI_ACCESS_KEY")
    secret_key: str = Field(..., env="HUAWEI_SECRET_KEY")
    project_id: str = Field(..., env="HUAWEI_PROJECT_ID")
    region: str = Field(default="cn-north-4", env="HUAWEI_REGION")

    class Config:
        env_file = ".env"
        case_sensitive = False


class AppConfig(BaseSettings):
    """Application configuration."""
    env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=True, env="APP_DEBUG")
    host: str = Field(default="0.0.0.0", env="APP_HOST")
    port: int = Field(default=8000, env="APP_PORT")

    class Config:
        env_file = ".env"
        case_sensitive = False


class APIConfig(BaseSettings):
    """API configuration."""
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    timeout: int = Field(default=180, env="API_TIMEOUT")  # 3 minutes

    class Config:
        env_file = ".env"
        case_sensitive = False


class StorageConfig(BaseSettings):
    """Storage configuration."""
    path: Path = Field(default=Path("./data/documents"), env="STORAGE_PATH")
    max_size_mb: int = Field(default=10, env="STORAGE_MAX_SIZE_MB")
    retention_days: int = Field(default=30, env="STORAGE_RETENTION_DAYS")

    @validator("path", pre=True)
    def create_path(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        case_sensitive = False


class QueueConfig(BaseSettings):
    """Queue configuration."""
    path: Path = Field(default=Path("./data/queue"), env="QUEUE_PATH")
    manual_review_threshold: float = Field(default=80.0, env="MANUAL_REVIEW_THRESHOLD")

    @validator("path", pre=True)
    def create_path(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @validator("manual_review_threshold")
    def validate_threshold(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Threshold must be between 0 and 100")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")
    path: Path = Field(default=Path("./data/logs"), env="LOG_PATH")
    max_size_mb: int = Field(default=100, env="LOG_MAX_SIZE_MB")
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")

    @validator("path", pre=True)
    def create_path(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @validator("level")
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    class Config:
        env_file = ".env"
        case_sensitive = False


class ProcessingConfig(BaseSettings):
    """Processing configuration."""
    timeout: int = Field(default=180, env="PROCESSING_TIMEOUT")  # 3 minutes
    target_time: int = Field(default=6, env="PROCESSING_TARGET_TIME")  # 6 seconds
    image_max_size_mb: int = Field(default=10, env="IMAGE_MAX_SIZE_MB")
    image_optimal_size_mb: int = Field(default=7, env="IMAGE_OPTIMAL_SIZE_MB")

    class Config:
        env_file = ".env"
        case_sensitive = False


class LanguageModelConfig(BaseSettings):
    """Language model configuration."""
    spacy_model_en: str = Field(default="en_core_web_sm", env="SPACY_MODEL_EN")
    spacy_model_zh: str = Field(default="zh_core_web_sm", env="SPACY_MODEL_ZH")

    class Config:
        env_file = ".env"
        case_sensitive = False


class ConfidenceWeights(BaseSettings):
    """Confidence scoring weights."""
    image_quality: float = Field(default=0.2, env="WEIGHT_IMAGE_QUALITY")
    ocr_confidence: float = Field(default=0.3, env="WEIGHT_OCR_CONFIDENCE")
    grammar_score: float = Field(default=0.2, env="WEIGHT_GRAMMAR_SCORE")
    context_score: float = Field(default=0.2, env="WEIGHT_CONTEXT_SCORE")
    structure_score: float = Field(default=0.1, env="WEIGHT_STRUCTURE_SCORE")

    @validator("image_quality", "ocr_confidence", "grammar_score", "context_score", "structure_score")
    def validate_weight(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v

    @validator("structure_score")
    def validate_total_weights(cls, v, values):
        total = (
            values.get("image_quality", 0) +
            values.get("ocr_confidence", 0) +
            values.get("grammar_score", 0) +
            values.get("context_score", 0) +
            v
        )
        if abs(total - 1.0) > 0.001:  # Allow small floating point errors
            raise ValueError(f"Total weights must equal 1.0, got {total}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


class Settings:
    """Application settings combining all configurations."""

    def __init__(self):
        """Initialize settings from environment."""
        try:
            self.huawei = HuaweiConfig()
        except Exception:
            # Allow running without Huawei config for development
            self.huawei = None

        self.app = AppConfig()
        self.api = APIConfig()
        self.storage = StorageConfig()
        self.queue = QueueConfig()
        self.logging = LoggingConfig()
        self.processing = ProcessingConfig()
        self.language_models = LanguageModelConfig()
        self.confidence_weights = ConfidenceWeights()

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app.env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app.env == "development"


# Create singleton instance
settings = Settings()