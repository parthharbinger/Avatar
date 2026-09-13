"""
Simli WebRTC Audio-to-Video Avatar Streaming Adapter.
Connects to Simli's low-latency (<300ms) WebRTC API.
"""
import aiohttp
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class SimliAvatarProvider(BaseAvatarProvider):
    """
    Simli WebRTC Streaming Avatar Provider.
    Documentation: https://docs.simli.com
    """

    BASE_URL = "https://api.simli.ai"
    _stream_sessions: Dict[str, str] = {}

    def __init__(self) -> None:
        self.api_key = settings.simli_api_key
        self.face_id = settings.simli_face_id

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WebRTC session on Simli."""
        if not self.api_key:
            raise ValueError("SIMLI_API_KEY is not configured in .env. Please add SIMLI_API_KEY to use Simli.")

        face_id = self.face_id
        if avatar_id and str(avatar_id).lower() in ("male", "david", "adam"):
            face_id = "tmp9i8bbq7v"  # Simli standard male face ID

        url = f"{self.BASE_URL}/startAudioToVideoSession"
        payload = {
            "faceId": face_id,
            "isJPG": False,
            "syncAudio": True,
            "handleSilence": True,
            "maxSessionLength": 3600,
            "maxIdleTime": 300,
        }

        logger.info("Creating Simli WebRTC stream", extra={"event": "simli_create_stream", "session_id": session_id})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("Simli create stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"Simli API error: {resp.status} - {err_text}")

                data = await resp.json()
                stream_id = data.get("session_id") or data.get("sessionId") or session_id
                self._stream_sessions[stream_id] = stream_id

                return {
                    "provider": "simli",
                    "stream_id": stream_id,
                    "offer": data.get("offer") or data.get("sdp"),
                    "ice_servers": data.get("ice_servers") or data.get("iceServers") or [{ "urls": ["stun:stun.l.google.com:19302"] }],
                    "did_session_id": stream_id,
                }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Submit SDP answer to Simli."""
        url = f"{self.BASE_URL}/submitAnswer"
        payload = {
            "sessionId": stream_id,
            "answer": answer_sdp,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.warning("Simli answer submission warning", extra={"status": resp.status, "error": err_text})

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """Submit ICE candidate to Simli."""
        url = f"{self.BASE_URL}/ice"
        payload = {
            "sessionId": stream_id,
            "candidate": candidate,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    pass

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Simli audio-to-video speak trigger."""
        url = f"{self.BASE_URL}/speak"
        payload = {
            "sessionId": stream_id,
            "text": text,
            "voice": voice or "en-US-JennyNeural",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("Simli speak failed", extra={"status": resp.status, "error": err_text})

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt active Simli speech."""
        url = f"{self.BASE_URL}/interrupt"
        payload = {"sessionId": stream_id}
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, headers=self._get_headers())
        except Exception:
            pass

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close Simli session."""
        url = f"{self.BASE_URL}/closeSession"
        payload = {"sessionId": stream_id}
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, headers=self._get_headers())
        except Exception:
            pass
        finally:
            self._stream_sessions.pop(stream_id, None)
