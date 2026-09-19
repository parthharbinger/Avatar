"""
Structured JSON logger setup for the application.
Emits formatted JSON logs to console stdout, app.log, and dedicated errors.log
for backtrack and diagnostic debugging.
"""
import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "data" / "logs"
APP_LOG_FILE = LOGS_DIR / "app.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"


def setup_logging() -> None:
    """Configure root logger with console, app.log, and dedicated errors.log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handlers = []

    # 1. Console Stream Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # 2. Main Rotating File Handler (data/logs/app.log - 10MB x 5 backups)
    try:
        app_file_handler = RotatingFileHandler(
            filename=str(APP_LOG_FILE),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        app_file_handler.setLevel(log_level)
        app_file_handler.setFormatter(formatter)
        handlers.append(app_file_handler)
    except Exception as e:
        sys.stderr.write(f"Failed to initialize app.log handler: {e}\n")

    # 3. Dedicated Error Rotating File Handler (data/logs/errors.log - 10MB x 5 backups)
    try:
        err_file_handler = RotatingFileHandler(
            filename=str(ERROR_LOG_FILE),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        err_file_handler.setLevel(logging.WARNING)
        err_file_handler.setFormatter(formatter)
        handlers.append(err_file_handler)
    except Exception as e:
        sys.stderr.write(f"Failed to initialize errors.log handler: {e}\n")

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = handlers

    # Suppress noisy third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)


def read_recent_logs(
    level: Optional[str] = None,
    search: Optional[str] = None,
    error_only: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Read and backtrack recent log records in reverse-chronological order.
    
    Args:
        level: Filter by log level (e.g. 'ERROR', 'WARNING', 'INFO')
        search: Keyword search string across message and details
        error_only: Read from dedicated errors.log instead of app.log
        limit: Maximum number of entries to return (default: 50, max: 500)
    """
    target_file = ERROR_LOG_FILE if error_only else APP_LOG_FILE
    if not target_file.exists():
        return []

    limit = max(1, min(limit, 500))
    search_lower = search.lower().strip() if search else None
    level_upper = level.upper().strip() if level else None

    results: List[Dict[str, Any]] = []

    try:
        # Read lines in reverse order for newest-first logs
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in reversed(lines):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                log_entry = json.loads(line_str)
            except Exception:
                log_entry = {"raw": line_str}

            # Filter by level
            if level_upper and log_entry.get("levelname", "").upper() != level_upper:
                continue

            # Filter by search keyword
            if search_lower:
                entry_str = json.dumps(log_entry).lower()
                if search_lower not in entry_str:
                    continue

            results.append(log_entry)
            if len(results) >= limit:
                break

    except Exception as e:
        results.append({"error": f"Failed reading log file: {str(e)}"})

    return results

