"""Logging configuration and utilities."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler

from src.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data["extra"] = record.extra_fields

        return json.dumps(log_data, default=str)


class Logger:
    """Logger factory with structured logging support."""

    _loggers: Dict[str, logging.Logger] = {}
    _initialized: bool = False

    @classmethod
    def _initialize(cls) -> None:
        """Initialize logging configuration."""
        if cls._initialized:
            return

        # Create logs directory
        log_path = settings.logging.path
        log_path.mkdir(parents=True, exist_ok=True)

        # Set base logging level
        logging.getLogger().setLevel(settings.logging.level)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str, log_to_file: bool = True) -> logging.Logger:
        """Get or create a logger with the given name.

        Args:
            name: Logger name (e.g., 'api', 'ocr', 'validation')
            log_to_file: Whether to log to file in addition to console

        Returns:
            Configured logger instance
        """
        cls._initialize()

        if name in cls._loggers:
            return cls._loggers[name]

        # Create new logger
        logger = logging.getLogger(name)
        logger.setLevel(settings.logging.level)
        logger.handlers = []  # Clear any existing handlers

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(settings.logging.level)

        if settings.logging.format == "json":
            console_formatter = JSONFormatter()
        else:
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler
        if log_to_file:
            log_file = settings.logging.path / f"{name}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=settings.logging.max_size_mb * 1024 * 1024,
                backupCount=settings.logging.backup_count,
            )
            file_handler.setLevel(settings.logging.level)

            if settings.logging.format == "json":
                file_formatter = JSONFormatter()
            else:
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def log_with_context(
        cls,
        logger: logging.Logger,
        level: str,
        message: str,
        **context: Any
    ) -> None:
        """Log a message with additional context.

        Args:
            logger: Logger instance
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            **context: Additional context to include in the log
        """
        record = logging.LogRecord(
            name=logger.name,
            level=getattr(logging, level.upper()),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.extra_fields = context
        logger.handle(record)


# Create default loggers
api_logger = Logger.get_logger("api")
ocr_logger = Logger.get_logger("ocr")
validation_logger = Logger.get_logger("validation")
queue_logger = Logger.get_logger("queue")
processing_logger = Logger.get_logger("processing")


class ProcessingTimer:
    """Context manager for timing operations and logging."""

    def __init__(
        self,
        operation: str,
        logger: Optional[logging.Logger] = None,
        log_level: str = "INFO"
    ):
        """Initialize timer.

        Args:
            operation: Name of the operation being timed
            logger: Logger to use (defaults to processing_logger)
            log_level: Level to log at (default INFO)
        """
        self.operation = operation
        self.logger = logger or processing_logger
        self.log_level = log_level
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.utcnow()
        Logger.log_with_context(
            self.logger,
            self.log_level,
            f"Starting {self.operation}",
            operation=self.operation,
            start_time=self.start_time.isoformat()
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log duration."""
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()

        if exc_type:
            Logger.log_with_context(
                self.logger,
                "ERROR",
                f"Failed {self.operation}",
                operation=self.operation,
                duration_seconds=duration,
                error=str(exc_val),
                error_type=exc_type.__name__
            )
        else:
            Logger.log_with_context(
                self.logger,
                self.log_level,
                f"Completed {self.operation}",
                operation=self.operation,
                duration_seconds=duration,
                end_time=self.end_time.isoformat()
            )

    @property
    def duration(self) -> Optional[float]:
        """Get operation duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


def log_document_processing(
    document_id: str,
    status: str,
    confidence: Optional[float] = None,
    routing: Optional[str] = None,
    error: Optional[str] = None,
    **extra: Any
) -> None:
    """Log document processing events.

    Args:
        document_id: Document identifier
        status: Processing status
        confidence: Confidence score if available
        routing: Routing decision if available
        error: Error message if failed
        **extra: Additional context
    """
    context = {
        "document_id": document_id,
        "status": status,
    }

    if confidence is not None:
        context["confidence"] = confidence
    if routing:
        context["routing"] = routing
    if error:
        context["error"] = error

    context.update(extra)

    level = "ERROR" if error else "INFO"
    message = f"Document {document_id}: {status}"

    Logger.log_with_context(processing_logger, level, message, **context)


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration: float,
    user_id: Optional[str] = None,
    error: Optional[str] = None,
    **extra: Any
) -> None:
    """Log API request details.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration: Request duration in seconds
        user_id: User identifier if authenticated
        error: Error message if failed
        **extra: Additional context
    """
    context = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_seconds": duration,
    }

    if user_id:
        context["user_id"] = user_id
    if error:
        context["error"] = error

    context.update(extra)

    level = "ERROR" if status_code >= 500 else "INFO"
    message = f"{method} {path} - {status_code}"

    Logger.log_with_context(api_logger, level, message, **context)


def log_ocr_processing(
    document_id: str,
    provider: str,
    duration: float,
    success: bool,
    confidence: Optional[float] = None,
    word_count: Optional[int] = None,
    error: Optional[str] = None,
    **extra: Any
) -> None:
    """Log OCR processing events.

    Args:
        document_id: Document identifier
        provider: OCR provider (e.g., 'huawei')
        duration: Processing duration in seconds
        success: Whether OCR was successful
        confidence: Average confidence if available
        word_count: Number of words extracted
        error: Error message if failed
        **extra: Additional context
    """
    context = {
        "document_id": document_id,
        "provider": provider,
        "duration_seconds": duration,
        "success": success,
    }

    if confidence is not None:
        context["confidence"] = confidence
    if word_count is not None:
        context["word_count"] = word_count
    if error:
        context["error"] = error

    context.update(extra)

    level = "ERROR" if not success else "INFO"
    message = f"OCR processing for {document_id}: {'Success' if success else 'Failed'}"

    Logger.log_with_context(ocr_logger, level, message, **context)


def log_validation(
    document_id: str,
    validation_type: str,
    score: float,
    issues: Optional[int] = None,
    language: Optional[str] = None,
    **extra: Any
) -> None:
    """Log validation events.

    Args:
        document_id: Document identifier
        validation_type: Type of validation (grammar, context, structure)
        score: Validation score
        issues: Number of issues found
        language: Detected language
        **extra: Additional context
    """
    context = {
        "document_id": document_id,
        "validation_type": validation_type,
        "score": score,
    }

    if issues is not None:
        context["issues"] = issues
    if language:
        context["language"] = language

    context.update(extra)

    message = f"Validation {validation_type} for {document_id}: score={score}"
    Logger.log_with_context(validation_logger, "INFO", message, **context)


def log_queue_event(
    queue_name: str,
    event_type: str,
    document_id: Optional[str] = None,
    priority: Optional[str] = None,
    queue_size: Optional[int] = None,
    **extra: Any
) -> None:
    """Log queue events.

    Args:
        queue_name: Name of the queue
        event_type: Type of event (added, removed, processed)
        document_id: Document identifier if applicable
        priority: Priority level
        queue_size: Current queue size
        **extra: Additional context
    """
    context = {
        "queue_name": queue_name,
        "event_type": event_type,
    }

    if document_id:
        context["document_id"] = document_id
    if priority:
        context["priority"] = priority
    if queue_size is not None:
        context["queue_size"] = queue_size

    context.update(extra)

    message = f"Queue {queue_name}: {event_type}"
    if document_id:
        message += f" document {document_id}"

    Logger.log_with_context(queue_logger, "INFO", message, **context)