import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    huawei_ocr_endpoint: str = Field(
        default=os.getenv("HUAWEI_OCR_ENDPOINT", "https://ocr.ap-southeast-3.myhuaweicloud.com")
    )
    huawei_access_key: str = Field(default=os.getenv("HUAWEI_ACCESS_KEY", ""))
    huawei_secret_key: str = Field(default=os.getenv("HUAWEI_SECRET_KEY", ""))
    huawei_project_id: str = Field(default=os.getenv("HUAWEI_PROJECT_ID", ""))
    huawei_region: str = Field(default=os.getenv("HUAWEI_REGION", "ap-southeast-3"))

    app_env: str = Field(default=os.getenv("APP_ENV", "development"))
    app_debug: bool = Field(default=os.getenv("APP_DEBUG", "false").lower() == "true")
    app_host: str = Field(default=os.getenv("APP_HOST", "0.0.0.0"))
    app_port: int = Field(default=int(os.getenv("APP_PORT", "8000")))

    api_key: Optional[str] = Field(default=os.getenv("API_KEY"))
    api_timeout: int = Field(default=int(os.getenv("API_TIMEOUT", "180")))

    storage_path: Path = Field(default=Path(os.getenv("STORAGE_PATH", "./data/documents")))
    storage_max_size_mb: int = Field(default=int(os.getenv("STORAGE_MAX_SIZE_MB", "10")))
    storage_retention_days: int = Field(default=int(os.getenv("STORAGE_RETENTION_DAYS", "30")))

    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = Field(default=os.getenv("LOG_FORMAT", "json"))
    log_path: Path = Field(default=Path(os.getenv("LOG_PATH", "./data/logs")))
    log_max_size_mb: int = Field(default=int(os.getenv("LOG_MAX_SIZE_MB", "100")))
    log_backup_count: int = Field(default=int(os.getenv("LOG_BACKUP_COUNT", "5")))

    processing_timeout: int = Field(default=int(os.getenv("PROCESSING_TIMEOUT", "180")))
    processing_target_time: int = Field(default=int(os.getenv("PROCESSING_TARGET_TIME", "6")))
    image_max_size_mb: int = Field(default=int(os.getenv("IMAGE_MAX_SIZE_MB", "10")))
    image_optimal_size_mb: int = Field(default=int(os.getenv("IMAGE_OPTIMAL_SIZE_MB", "7")))

    obs_bucket_name: str = Field(default=os.getenv("OBS_BUCKET_NAME", "sample-dataset-bucket"))
    obs_endpoint: str = Field(default=os.getenv("OBS_ENDPOINT", "https://obs.ap-southeast-3.myhuaweicloud.com"))

    # LLM Configuration (Huawei ModelArts MAAS)
    maas_api_key: Optional[str] = Field(default=os.getenv("MAAS_API_KEY", None))
    maas_base_url: Optional[str] = Field(default=os.getenv("MAAS_BASE_URL", None))
    maas_model_name: str = Field(default=os.getenv("MAAS_MODEL_NAME", "DeepSeek-V3"))
    llm_temperature: float = Field(default=float(os.getenv("LLM_TEMPERATURE", "0.1")))
    llm_max_tokens: int = Field(default=int(os.getenv("LLM_MAX_TOKENS", "4096")))
    llm_timeout: int = Field(default=int(os.getenv("LLM_TIMEOUT", "30")))

    # Format Support Configuration
    supported_formats: list[str] = Field(
        default=os.getenv("SUPPORTED_FORMATS", "PNG,JPG,JPEG,BMP,GIF,TIFF,WebP,PCX,ICO,PSD,PDF").split(",")
    )
    pdf_max_pages_auto_process: int = Field(default=int(os.getenv("PDF_MAX_PAGES_AUTO_PROCESS", "20")))
    pdf_parallel_pages: int = Field(default=int(os.getenv("PDF_PARALLEL_PAGES", "4")))
    auto_rotation: bool = Field(default=os.getenv("AUTO_ROTATION", "true").lower() == "true")
    max_batch_size: int = Field(default=int(os.getenv("MAX_BATCH_SIZE", "20")))

    # History Database Configuration
    history_db_path: Path = Field(default=Path(os.getenv("HISTORY_DB_PATH", "./data/history.db")))
    history_retention_days: int = Field(default=int(os.getenv("HISTORY_RETENTION_DAYS", "7")))
    history_cleanup_on_startup: bool = Field(
        default=os.getenv("HISTORY_CLEANUP_ON_STARTUP", "true").lower() == "true"
    )

    # Format Support Configuration
    supported_formats: list[str] = Field(
        default=os.getenv("SUPPORTED_FORMATS", "PNG,JPG,JPEG,BMP,GIF,TIFF,WebP,PCX,ICO,PSD,PDF").split(",")
    )
    pdf_max_pages_auto_process: int = Field(default=int(os.getenv("PDF_MAX_PAGES_AUTO_PROCESS", "20")))
    pdf_parallel_pages: int = Field(default=int(os.getenv("PDF_PARALLEL_PAGES", "4")))
    auto_rotation: bool = Field(default=os.getenv("AUTO_ROTATION", "true").lower() == "true")
    max_batch_size: int = Field(default=int(os.getenv("MAX_BATCH_SIZE", "20")))

    # History Database Configuration
    history_db_path: Path = Field(default=Path(os.getenv("HISTORY_DB_PATH", "./data/history.db")))
    history_retention_days: int = Field(default=int(os.getenv("HISTORY_RETENTION_DAYS", "7")))
    history_cleanup_on_startup: bool = Field(
        default=os.getenv("HISTORY_CLEANUP_ON_STARTUP", "true").lower() == "true"
    )

    # Format Support Configuration
    supported_formats: str = Field(default=os.getenv("SUPPORTED_FORMATS", "PNG,JPG,JPEG,BMP,GIF,TIFF,WebP,PCX,ICO,PSD,PDF"))
    pdf_max_pages_auto_process: int = Field(default=int(os.getenv("PDF_MAX_PAGES_AUTO_PROCESS", "20")))
    pdf_parallel_pages: int = Field(default=int(os.getenv("PDF_PARALLEL_PAGES", "4")))
    auto_rotation: bool = Field(default=os.getenv("AUTO_ROTATION", "true").lower() == "true")
    max_batch_size: int = Field(default=int(os.getenv("MAX_BATCH_SIZE", "20")))

    # History Database Configuration
    history_db_path: Path = Field(default=Path(os.getenv("HISTORY_DB_PATH", "./data/history.db")))
    history_retention_days: int = Field(default=int(os.getenv("HISTORY_RETENTION_DAYS", "7")))
    history_cleanup_on_startup: bool = Field(default=os.getenv("HISTORY_CLEANUP_ON_STARTUP", "true").lower() == "true")

    @field_validator("storage_path", "log_path", "history_db_path", mode='before')
    def create_directories(cls, v):
        path = Path(v)
        # For database files, create parent directory only
        if str(path).endswith('.db'):
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("history_db_path", mode='before')
    def create_history_db_directory(cls, v):
        path = Path(v)
        # Create parent directory for database file
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("weight_image_quality", "weight_ocr_confidence", "weight_grammar_score",
                     "weight_context_score", "weight_structure_score")
    def validate_weights(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Weights must be between 0 and 1")
        return v

    @property
    def ocr_url(self) -> str:
        return f"{self.huawei_ocr_endpoint}/v2/{self.huawei_project_id}/ocr/smart-document-recognizer"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


settings = Settings()