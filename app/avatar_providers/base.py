"""
Abstract base for photorealistic WebRTC avatar video providers (D-ID, HeyGen, etc.).
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseAvatarProvider(ABC):
    @abstractmethod
    async def create_stream(self, session_id: str, avatar_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a WebRTC streaming session with the provider.
        Returns connection details (offer, stream_id, ice_servers, etc.).
        """
        ...

    @abstractmethod
    async def start_stream(self, stream_id: str, answer_sdp: Dict[str, Any], session_id: str) -> None:
        """Start the WebRTC video stream by sending the client's SDP answer."""
        ...

    @abstractmethod
    async def submit_ice_candidate(self, stream_id: str, candidate: Dict[str, Any], session_id: str) -> None:
        """Submit an ICE candidate to the provider."""
        ...

    @abstractmethod
    async def speak(self, stream_id: str, text: str, voice: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Make the avatar speak the provided text in the live video stream."""
        ...

    @abstractmethod
    async def interrupt(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Interrupt active speech."""
        ...

    @abstractmethod
    async def close_stream(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """Close and tear down the streaming session."""
        ...
