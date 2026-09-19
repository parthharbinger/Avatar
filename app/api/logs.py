"""
Log Inspection and Backtrack API Router.
Provides structured diagnostic querying and error backtracking capabilities.
"""
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.auth.models import UserRole
from app.auth.dependencies import require_role, get_current_user
from app.logging_config import (
    read_recent_logs,
    APP_LOG_FILE,
    ERROR_LOG_FILE,
    get_logger,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/logs", tags=["Logs & Diagnostics"])


@router.get(
    "",
    summary="Query recent structured application logs with filtering & backtracking",
)
async def get_logs(
    level: Optional[str] = Query(
        None,
        description="Filter by log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    ),
    search: Optional[str] = Query(
        None,
        description="Keyword search across log messages and JSON payloads (e.g. session_id, error name)",
    ),
    error_only: bool = Query(
        False,
        description="If True, queries exclusively from dedicated errors.log",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Number of recent records to retrieve (reverse-chronological)",
    ),
):
    """
    Returns recent structured log entries in reverse chronological order (newest first).
    Allows fast backtracking and root-cause analysis for runtime errors, WebRTC handshakes,
    and LLM/RAG responses.
    """
    logs = read_recent_logs(
        level=level,
        search=search,
        error_only=error_only,
        limit=limit,
    )
    return {
        "count": len(logs),
        "source": "errors.log" if error_only else "app.log",
        "filter": {"level": level, "search": search, "limit": limit},
        "logs": logs,
    }


@router.get(
    "/errors",
    summary="Dedicated error backtrack endpoint (WARNING, ERROR, CRITICAL)",
)
async def get_error_logs(
    search: Optional[str] = Query(
        None,
        description="Keyword search across error messages and exception tracebacks",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Max errors to retrieve",
    ),
):
    """
    Quickly retrieves errors and warnings from the isolated data/logs/errors.log.
    """
    errors = read_recent_logs(
        search=search,
        error_only=True,
        limit=limit,
    )
    return {
        "count": len(errors),
        "source": "errors.log",
        "filter": {"search": search, "limit": limit},
        "errors": errors,
    }


@router.delete(
    "/clear",
    summary="Clear or truncate log files (Admin only)",
)
async def clear_logs(
    target: str = Query("all", pattern="^(all|app|errors)$"),
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    """
    Truncates log files for fresh debugging sessions.
    """
    cleared = []
    if target in ("all", "app") and APP_LOG_FILE.exists():
        with open(APP_LOG_FILE, "w", encoding="utf-8") as f:
            f.truncate(0)
        cleared.append("app.log")

    if target in ("all", "errors") and ERROR_LOG_FILE.exists():
        with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
            f.truncate(0)
        cleared.append("errors.log")

    logger.info("Logs cleared by admin", extra={"admin_id": admin["id"], "target": target})
    return {"status": "success", "cleared": cleared}
