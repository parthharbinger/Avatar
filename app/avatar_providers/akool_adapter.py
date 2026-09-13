"""
Akool Streaming Avatar & Talking Photo Adapter.
Connects to Akool OpenAPI.
"""
import aiohttp
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class AkoolAvatarProvider(BaseAvatarProvider):
    """
    Akool Avatar Streaming & Video Generation Provider.
    Documentation: https://docs.akool.com
    """

    BASE_URL = "https://openapi.akool.com/api/v1"
    _stream_sessions: Dict[str, str] = {}

    def __init__(self) -> None:
        self.api_key = settings.akool_api_key
        self.client_id = settings.akool_client_id

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a streaming session on Akool."""
        if not self.api_key:
            raise ValueError("AKOOL_API_KEY is not configured in .env. Please add AKOOL_API_KEY to use Akool.")

        url = f"{self.BASE_URL}/avatar/streaming/create"
        payload = {
            "avatar_id": "avatar_male_01" if avatar_id and str(avatar_id).lower() in ("male", "david", "adam") else "avatar_female_01",
            "session_id": session_id,
        }

        logger.info("Creating Akool streaming session", extra={"event": "akool_create_stream", "session_id": session_id})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("Akool create stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"Akool API error: {resp.status} - {err_text}")

                data = await resp.json()
                stream_id = data.get("stream_id") or data.get("session_id") or session_id
                self._stream_sessions[stream_id] = stream_id

                return {
                    "provider": "akool",
                    "stream_id": stream_id,
                    "offer": data.get("offer") or data.get("sdp"),
                    "ice_servers": data.get("ice_servers", [{ "urls": ["stun:stun.l.google.com:19302"] }]),
                    "did_session_id": stream_id,
                }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Submit SDP answer to Akool."""
        url = f"{self.BASE_URL}/avatar/streaming/{stream_id}/sdp"
        payload = {"answer": answer_sdp}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.warning("Akool answer submission warning", extra={"status": resp.status, "error": err_text})

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """Submit ICE candidate to Akool."""
        url = f"{self.BASE_URL}/avatar/streaming/{stream_id}/ice"
        payload = {"candidate": candidate}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                pass

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Make Akool avatar speak text."""
        url = f"{self.BASE_URL}/avatar/streaming/{stream_id}/talk"
        payload = {"text": text, "voice": voice or "en-US-JennyNeural"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("Akool speak failed", extra={"status": resp.status, "error": err_text})

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt active Akool speech."""
        url = f"{self.BASE_URL}/avatar/streaming/{stream_id}/interrupt"
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={}, headers=self._get_headers())
        except Exception:
            pass

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close Akool streaming session."""
        url = f"{self.BASE_URL}/avatar/streaming/{stream_id}/close"
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={}, headers=self._get_headers())
        except Exception:
            pass
        finally:
            self._stream_sessions.pop(stream_id, None)
