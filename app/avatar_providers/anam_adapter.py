"""
Anam.ai Real-Time Conversational Digital Human WebRTC Adapter.
Connects to Anam.ai's Session & Streaming Gateway.
"""
import aiohttp
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Default verified Anam.ai Avatars and Voices
ANAM_AVATAR_FEMALE = "edf6fdcb-acab-44b8-b974-ded72665ee26"  # Mia
ANAM_VOICE_FEMALE = "de23e340-1416-4dd8-977d-065a7ca11697"   # Lucy

ANAM_AVATAR_MALE = "6cc28442-cccd-42a8-b6e4-24b7210a09c5"    # Gabriel
ANAM_VOICE_MALE = "91b4ce0f-4fc0-11f1-84b0-52bacf74fa75"     # Archie


class AnamAvatarProvider(BaseAvatarProvider):
    """
    Anam.ai Real-Time WebRTC Digital Human Provider.
    Documentation: https://docs.anam.ai
    """

    BASE_URL = "https://api.anam.ai/v1"
    _stream_sessions: Dict[str, str] = {}

    def __init__(self) -> None:
        self.api_key = settings.anam_api_key.strip() if settings.anam_api_key else ""
        self.persona_id = settings.anam_persona_id

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WebRTC session token on Anam.ai."""
        if not self.api_key:
            raise ValueError("ANAM_API_KEY is not configured in .env. Please add ANAM_API_KEY to use Anam.ai.")

        is_male = bool(avatar_id and str(avatar_id).lower() in ("male", "david", "adam"))
        
        # If user explicitly supplied custom persona_id in .env
        if self.persona_id and self.persona_id != "default":
            payload = {"personaId": self.persona_id}
        else:
            payload = {
                "personaConfig": {
                    "name": "David" if is_male else "Emma",
                    "avatarId": ANAM_AVATAR_MALE if is_male else ANAM_AVATAR_FEMALE,
                    "voiceId": ANAM_VOICE_MALE if is_male else ANAM_VOICE_FEMALE,
                    "systemPrompt": "You are a helpful, natural, and concise AI conversational concierge.",
                }
            }

        url = f"{self.BASE_URL}/auth/session-token"
        logger.info("Creating Anam.ai stream token", extra={"event": "anam_create_stream", "session_id": session_id, "is_male": is_male})

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error("Anam.ai session token failed", extra={"status": resp.status, "error": err_text})
                    raise RuntimeError(f"Anam.ai API error: {resp.status} - {err_text}")

                data = await resp.json()
                session_token = data.get("sessionToken", "")
                self._stream_sessions[session_id] = session_token

                return {
                    "provider": "anam",
                    "stream_id": session_id,
                    "session_token": session_token,
                    "offer": {"type": "session_token", "session_token": session_token},
                    "ice_servers": [{"urls": ["stun:stun.l.google.com:19302"]}],
                    "did_session_id": session_id,
                }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Start stream lifecycle."""
        pass

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """Submit ICE candidate."""
        pass

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Make Anam avatar speak text."""
        pass

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt active speech."""
        pass

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close Anam session."""
        self._stream_sessions.pop(stream_id, None)
