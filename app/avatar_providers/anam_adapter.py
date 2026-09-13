"""
Anam.ai Real-Time Conversational Digital Human WebRTC Adapter.
Connects to Anam.ai's Streaming Engine.
"""
from typing import Optional, Dict, Any

from app.avatar_providers.base import BaseAvatarProvider
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Pre-configured Verified Personas on Anam.ai Gateway
ANAM_PERSONA_FEMALE = "db31ef59-e155-46a7-9e3b-88f80e825fde"  # Emma Concierge (Mia / Lucy)
ANAM_PERSONA_MALE = "60885ea5-fffd-4afd-b1d4-7b03ce80babc"    # David Concierge (Gabriel / Archie)

ANAM_AVATAR_FEMALE = "edf6fdcb-acab-44b8-b974-ded72665ee26"   # Mia
ANAM_VOICE_FEMALE = "de23e340-1416-4dd8-977d-065a7ca11697"    # Lucy

ANAM_AVATAR_MALE = "6cc28442-cccd-42a8-b6e4-24b7210a09c5"     # Gabriel
ANAM_VOICE_MALE = "91b4ce0f-4fc0-11f1-84b0-52bacf74fa75"      # Archie


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
        """Create a new WebRTC session on Anam.ai."""
        if not self.api_key:
            raise ValueError("ANAM_API_KEY is not configured in .env. Please add ANAM_API_KEY to use Anam.ai.")

        is_male = bool(avatar_id and str(avatar_id).lower() in ("male", "david", "adam"))
        
        # Determine target persona ID
        if self.persona_id and self.persona_id != "default":
            target_persona_id = self.persona_id
        else:
            target_persona_id = ANAM_PERSONA_MALE if is_male else ANAM_PERSONA_FEMALE

        logger.info(
            "Configuring Anam.ai digital human stream",
            extra={"event": "anam_create_stream", "session_id": session_id, "persona_id": target_persona_id, "is_male": is_male},
        )

        return {
            "provider": "anam",
            "stream_id": session_id,
            "api_key": self.api_key,
            "persona_id": target_persona_id,
            "persona_config": {
                "personaId": target_persona_id,
            },
            "did_session_id": session_id,
        }

    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        pass

    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        pass

    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        pass

    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        pass

    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        self._stream_sessions.pop(stream_id, None)
