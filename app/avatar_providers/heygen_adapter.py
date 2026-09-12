"""
HeyGen WebRTC Streaming Avatar Adapter.
Connects to HeyGen's Interactive Avatar Streaming API to stream studio-quality avatars over WebRTC.
"""
import aiohttp
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class HeyGenAvatarProvider(BaseAvatarProvider):
    """
    HeyGen Interactive Streaming Avatar Provider.
    """

    BASE_URL = "https://api.heygen.com/v1"

    def __init__(self) -> None:
        self.api_key = settings.heygen_api_key
        self.avatar_id = settings.heygen_avatar_id

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new streaming session with HeyGen."""
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY is not configured in .env")

        url = f"{self.BASE_URL}/streaming.new"
        payload = {
            "avatar_name": avatar_id or self.avatar_id,
            "quality": "medium",
        }

        logger.info("Creating HeyGen stream", extra={"event": "heygen_create_stream", "session_id": session_id})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("HeyGen create stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"HeyGen API error: {resp.status} - {err_text}")

                res_json = await resp.json()
                data = res_json.get("data", {})
                return {
                    "provider": "heygen",
                    "stream_id": data.get("session_id"),
                    "offer": data.get("sdp"),
                    "ice_servers": data.get("ice_servers2", []),
                }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Send SDP answer to HeyGen to start live WebRTC video stream."""
        url = f"{self.BASE_URL}/streaming.start"
        payload = {
            "session_id": stream_id,
            "sdp": answer_sdp,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("HeyGen start stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"HeyGen SDP start error: {resp.status} - {err_text}")

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """HeyGen handles ICE candidates via standard WebRTC negotiation."""
        pass

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Send speech task to HeyGen streaming avatar."""
        url = f"{self.BASE_URL}/streaming.task"
        payload = {
            "session_id": stream_id,
            "text": text,
            "task_type": "talk",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("HeyGen speak failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"HeyGen speak error: {resp.status} - {err_text}")

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt active HeyGen avatar speech."""
        url = f"{self.BASE_URL}/streaming.interrupt"
        payload = {"session_id": stream_id}

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, headers=self._get_headers())
        except Exception as e:
            logger.warning(f"Error interrupting HeyGen stream: {e}")

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close HeyGen streaming session."""
        if not stream_id:
            return
        url = f"{self.BASE_URL}/streaming.stop"
        payload = {"session_id": stream_id}

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, headers=self._get_headers())
        except Exception as e:
            logger.warning(f"Error closing HeyGen stream: {e}")
