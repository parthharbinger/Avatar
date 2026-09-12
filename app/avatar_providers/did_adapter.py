"""
D-ID WebRTC Streaming Adapter.
Connects to D-ID's Talks/Streams API to stream photorealistic neural talking video directly over WebRTC.
"""
import base64
import aiohttp
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class DIDAvatarProvider(BaseAvatarProvider):
    """
    D-ID WebRTC Streaming Avatar Provider.
    """

    BASE_URL = "https://api.d-id.com"

    def __init__(self) -> None:
        self.api_key = settings.did_api_key
        self.source_url = settings.did_source_url

    def _get_headers(self) -> Dict[str, str]:
        # D-ID expects Basic auth or raw key
        if ":" in self.api_key:
            auth_bytes = base64.b64encode(self.api_key.encode("utf-8")).decode("utf-8")
            auth_header = f"Basic {auth_bytes}"
        else:
            auth_header = f"Basic {self.api_key}"

        return {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WebRTC streaming session on D-ID."""
        if not self.api_key:
            raise ValueError("DID_API_KEY is not configured in .env")

        if avatar_id in ("male", "david", "adam"):
            src_url = "https://clips-presenters.d-id.com/v2/Adam/0GLJgELXjc/j0HIbyxjap/image.png"
        else:
            src_url = self.source_url or "https://clips-presenters.d-id.com/v2/Alyssa_NoHands_BlackShirt_Home/Mvn6Nalx90/y0J6MTfOaZ/image.png"

        url = f"{self.BASE_URL}/talks/streams"
        payload = {
            "source_url": src_url,
            "driver_url": "bank://lively",
        }

        logger.info("Creating D-ID stream", extra={"event": "did_create_stream", "session_id": session_id})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("D-ID create stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"D-ID API error: {resp.status} - {err_text}")

                data = await resp.json()
                return {
                    "provider": "d-id",
                    "stream_id": data.get("id"),
                    "offer": data.get("offer"),
                    "ice_servers": data.get("ice_servers", []),
                    "did_session_id": data.get("session_id"),
                }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Submit WebRTC answer SDP to D-ID to establish P2P connection."""
        url = f"{self.BASE_URL}/talks/streams/{stream_id}/sdp"
        payload = {
            "answer": answer_sdp,
            "session_id": session_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("D-ID start stream failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"D-ID SDP error: {resp.status} - {err_text}")

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """Submit ICE candidate to D-ID."""
        url = f"{self.BASE_URL}/talks/streams/{stream_id}/ice"
        payload = {
            "candidate": candidate.get("candidate"),
            "sdpMid": candidate.get("sdpMid"),
            "sdpMLineIndex": candidate.get("sdpMLineIndex"),
            "session_id": session_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.warning("D-ID submit ICE candidate warning", extra={"status": resp.status, "error": err_text})

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Send speech text to D-ID talking avatar."""
        url = f"{self.BASE_URL}/talks/streams/{stream_id}"
        voice_id = voice or "en-US-JennyNeural"

        payload = {
            "script": {
                "type": "text",
                "input": text,
                "provider": {
                    "type": "microsoft",
                    "voice_id": voice_id,
                },
            },
            "driver_url": "bank://lively",
            "session_id": session_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("D-ID speak failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"D-ID speak error: {resp.status} - {err_text}")

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt current speech in D-ID."""
        # D-ID automatically handles speech queueing / interruption
        pass

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close D-ID WebRTC stream."""
        if not stream_id:
            return
        url = f"{self.BASE_URL}/talks/streams/{stream_id}"
        payload = {"session_id": session_id} if session_id else {}

        try:
            async with aiohttp.ClientSession() as session:
                await session.delete(url, json=payload, headers=self._get_headers())
        except Exception as e:
            logger.warning(f"Error closing D-ID stream: {e}")
