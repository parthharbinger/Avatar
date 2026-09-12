"""
Abstract TTS adapter interface.
Implement this to swap between Edge-TTS, ElevenLabs, or any other provider
without changing any orchestration or WebSocket code.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from dataclasses import dataclass


@dataclass
class AudioChunk:
    """A chunk of audio data streaming from the TTS provider."""
    data: bytes           # Raw audio bytes (MP3 or WAV)
    chunk_index: int      # Sequential index for ordering
    is_final: bool = False  # True on the last chunk


class BaseTTSAdapter(ABC):
    """
    Abstract base for all TTS providers.
    Implementations must stream audio as AsyncGenerator[AudioChunk].
    """

    @abstractmethod
    async def stream_speech(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """
        Convert text to speech, streaming audio chunks as they are generated.

        Args:
            text: The text to synthesize.

        Yields:
            AudioChunk objects containing raw audio bytes.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this TTS provider."""
        ...
