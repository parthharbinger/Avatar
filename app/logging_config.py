"""
Structured JSON logger setup for the application.
All logs emitted as JSON for easy ingestion by log aggregators.
"""
import logging
import sys
try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter

from app.config import settings


def setup_logging() -> None:
    """Configure root logger with JSON formatting."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Suppress noisy third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)
