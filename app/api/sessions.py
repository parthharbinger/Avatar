"""
REST API routes for session lifecycle management.
"""
import asyncio
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.sessions.manager import session_manager, SessionLimitExceededError, SessionNotFoundError
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    avatar_id: str = Field(default="default", description="Avatar identity to use for this session.")


class CreateSessionResponse(BaseModel):
    session_id: str
    avatar_id: str
    ws_url: str
    state: str


class SessionInfoResponse(BaseModel):
    session_id: str
    state: str
    avatar_id: str


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new avatar session",
    description="Creates a new session and returns the WebSocket URL to connect to.",
)
async def create_session(body: CreateSessionRequest = CreateSessionRequest()):
    try:
        session = await session_manager.create_session(avatar_id=body.avatar_id)
        return CreateSessionResponse(
            session_id=session.session_id,
            avatar_id=session.avatar_id,
            ws_url=f"/api/v1/stream/{session.session_id}",
            state=session.state.value,
        )
    except SessionLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error("Failed to create session", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.get(
    "/sessions/{session_id}",
    response_model=SessionInfoResponse,
    summary="Get session info",
)
async def get_session(session_id: str):
    try:
        session = await session_manager.get_session(session_id)
        return SessionInfoResponse(
            session_id=session.session_id,
            state=session.state.value,
            avatar_id=session.avatar_id,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate a session",
)
async def delete_session(session_id: str):
    try:
        await session_manager.remove_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
