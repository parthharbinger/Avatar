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


from typing import Optional, Dict, Any, List
from app.avatar_providers import get_avatar_provider
from app.config import settings


@router.get(
    "/providers",
    summary="List all available avatar engines and API key configuration status",
)
async def list_providers():
    """
    Returns list of all supported avatar streaming engines, their latency tiers,
    and whether their API key is currently detected and configured in .env.
    """
    return {
        "active_default": settings.avatar_provider,
        "providers": [
            {
                "id": "d-id",
                "name": "D-ID",
                "label": "🎬 D-ID (Photorealistic WebRTC Video)",
                "type": "webrtc",
                "configured": bool(settings.did_api_key and settings.did_api_key.strip()),
                "latency": "< 450ms",
                "description": "Photorealistic AI digital humans with natural expressions and head movement.",
            },
            {
                "id": "anam",
                "name": "Anam.ai",
                "label": "🤖 Anam.ai (Digital Human WebRTC)",
                "type": "webrtc",
                "configured": bool(settings.anam_api_key and settings.anam_api_key.strip()),
                "latency": "< 350ms",
                "description": "Next-generation ultra-realistic conversational digital humans.",
            },
            {
                "id": "simli",
                "name": "Simli",
                "label": "⚡ Simli (Ultra-Low Latency <300ms)",
                "type": "webrtc",
                "configured": bool(settings.simli_api_key and settings.simli_api_key.strip()),
                "latency": "< 300ms",
                "description": "Sub-second audio-to-video neural avatar rendering via WebRTC.",
            },
            {
                "id": "akool",
                "name": "Akool",
                "label": "🎥 Akool (Streaming Avatar)",
                "type": "webrtc",
                "configured": bool(settings.akool_api_key and settings.akool_api_key.strip()),
                "latency": "< 500ms",
                "description": "High fidelity streaming avatar with real-time lip synchronisation.",
            },
            {
                "id": "heygen",
                "name": "HeyGen",
                "label": "🎞️ HeyGen (Interactive WebRTC Video)",
                "type": "webrtc",
                "configured": bool(settings.heygen_api_key and settings.heygen_api_key.strip()),
                "latency": "< 600ms",
                "description": "Studio-quality interactive avatar video streaming.",
            },
            {
                "id": "edge-tts",
                "name": "Lightweight 2D Canvas",
                "label": "⚡ Lightweight 2D Canvas ($0 Unmetered)",
                "type": "canvas",
                "configured": True,
                "latency": "< 180ms",
                "description": "Zero external credits required. 24kHz HD Edge-TTS + word-boundary lip sync.",
            },
        ],
    }


class WebRTCOfferResponse(BaseModel):
    provider: str
    stream_id: str
    offer: Optional[Dict[str, Any]] = None
    ice_servers: Optional[list] = None
    did_session_id: Optional[str] = None
    session_token: Optional[str] = None
    api_key: Optional[str] = None
    persona_id: Optional[str] = None
    persona_config: Optional[Dict[str, Any]] = None


class WebRTCAnswerRequest(BaseModel):
    stream_id: str
    answer: Dict[str, Any]
    provider_session_id: Optional[str] = None


class WebRTCIceRequest(BaseModel):
    stream_id: str
    candidate: Dict[str, Any]
    provider_session_id: Optional[str] = None


class WebRTCSpeakRequest(BaseModel):
    stream_id: str
    text: str
    voice: Optional[str] = None
    provider_session_id: Optional[str] = None


@router.post(
    "/sessions/{session_id}/webrtc/offer",
    response_model=WebRTCOfferResponse,
    summary="Create WebRTC Stream Offer (D-ID / HeyGen)",
)
async def create_webrtc_offer(session_id: str, avatar_id: Optional[str] = None, provider: Optional[str] = None):
    """
    Initialize WebRTC streaming session with configured provider (D-ID or HeyGen).
    """
    provider_adapter = get_avatar_provider(provider)
    if not provider_adapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No WebRTC avatar provider configured in .env (AVATAR_PROVIDER is set to edge-tts/canvas).",
        )

    try:
        effective_avatar_id = avatar_id
        if not effective_avatar_id:
            try:
                session = await session_manager.get_session(session_id)
                effective_avatar_id = session.avatar_id
            except Exception:
                pass

        data = await provider_adapter.create_stream(session_id=session_id, avatar_id=effective_avatar_id)
        return WebRTCOfferResponse(**data)
    except Exception as e:
        logger.error("WebRTC offer creation failed", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/sessions/{session_id}/webrtc/answer",
    summary="Submit WebRTC SDP Answer",
)
async def submit_webrtc_answer(session_id: str, body: WebRTCAnswerRequest, provider: Optional[str] = None):
    """
    Submit client's SDP answer to start live WebRTC video stream.
    """
    provider_adapter = get_avatar_provider(provider)
    if not provider_adapter:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No WebRTC provider configured.")

    try:
        await provider_adapter.start_stream(
            stream_id=body.stream_id,
            answer_sdp=body.answer,
            session_id=body.provider_session_id or session_id,
        )
        return {"status": "streaming_started"}
    except Exception as e:
        logger.error("WebRTC answer submission failed", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/sessions/{session_id}/webrtc/ice",
    summary="Submit WebRTC ICE Candidate",
)
async def submit_webrtc_ice(session_id: str, body: WebRTCIceRequest, provider: Optional[str] = None):
    provider_adapter = get_avatar_provider(provider)
    if not provider_adapter:
        return {"status": "ignored"}

    try:
        await provider_adapter.submit_ice_candidate(
            stream_id=body.stream_id,
            candidate=body.candidate,
            session_id=body.provider_session_id or session_id,
        )
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"ICE candidate error: {e}")
        return {"status": "error", "detail": str(e)}


@router.post(
    "/sessions/{session_id}/webrtc/speak",
    summary="Make WebRTC Avatar Speak",
)
async def webrtc_speak(session_id: str, body: WebRTCSpeakRequest, provider: Optional[str] = None):
    provider_adapter = get_avatar_provider(provider)
    if not provider_adapter:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No WebRTC provider configured.")

    try:
        await provider_adapter.speak(
            stream_id=body.stream_id,
            text=body.text,
            voice=body.voice,
            session_id=body.provider_session_id or session_id,
        )
        return {"status": "speech_dispatched"}
    except Exception as e:
        logger.error("WebRTC speak failed", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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
