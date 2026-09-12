"""
Edge-TTS adapter — streams MP3 audio chunks from Microsoft's free neural TTS.
No API key required. Uses the edge-tts Python library.
"""
import asyncio
import ssl
from typing import AsyncGenerator, Optional

import aiohttp
import edge_tts
import edge_tts.communicate

from app.tts.base import BaseTTSAdapter, AudioChunk
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class EdgeTTSAdapter(BaseTTSAdapter):
    """
    Edge-TTS (Microsoft Neural TTS) streaming adapter.
    Returns MP3 audio in ~4KB chunks at ~4KB/s for a typical speaking pace.
    """

    def __init__(self) -> None:
        self._voice = settings.edge_tts_voice
        if not settings.edge_tts_verify_ssl:
            try:
                edge_tts.communicate._SSL_CTX.check_hostname = False
                edge_tts.communicate._SSL_CTX.verify_mode = ssl.CERT_NONE
            except Exception as e:
                logger.warning(f"Could not configure SSL verification on edge-tts: {e}")

    def get_provider_name(self) -> str:
        return "edge-tts"

    async def stream_speech_with_boundaries(
        self, text: str, voice: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Stream TTS audio chunks along with exact WordBoundary timestamps from Edge-TTS.

        Yields:
            Dicts with:
              - {"type": "word_boundary", "word": str, "offset_ms": float, "duration_ms": float}
              - {"type": "audio", "data": bytes, "chunk_index": int}
              - {"type": "final", "total_chunks": int}
        """
        selected_voice = voice or self._voice
        logger.info(
            "EdgeTTS stream_speech_with_boundaries called",
            extra={"event": "tts_start", "provider": "edge-tts", "voice": selected_voice, "text_len": len(text)},
        )

        ssl_param = False if not settings.edge_tts_verify_ssl else None
        connector = aiohttp.TCPConnector(ssl=ssl_param)
        chunk_index = 0

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=selected_voice,
                boundary="WordBoundary",
                connector=connector,
            )

            async for chunk in communicate.stream():
                chunk_type = chunk.get("type")
                if chunk_type == "WordBoundary":
                    yield {
                        "type": "word_boundary",
                        "word": chunk.get("text", ""),
                        "offset_ms": chunk.get("offset", 0) / 10000.0,
                        "duration_ms": chunk.get("duration", 0) / 10000.0,
                    }
                elif chunk_type == "audio" and chunk.get("data"):
                    yield {
                        "type": "audio",
                        "data": chunk["data"],
                        "chunk_index": chunk_index,
                    }
                    chunk_index += 1

            yield {"type": "final", "total_chunks": chunk_index}
            logger.info(
                "EdgeTTS stream complete",
                extra={"event": "tts_end", "chunks": chunk_index},
            )

        except asyncio.CancelledError:
            logger.info(
                "EdgeTTS stream cancelled (barge-in)",
                extra={"event": "tts_cancelled"},
            )
            raise
        except Exception as e:
            logger.error(
                "EdgeTTS stream error",
                extra={"event": "tts_error", "error": str(e)},
            )
            raise

    async def stream_speech(self, text: str, voice: Optional[str] = None) -> AsyncGenerator[AudioChunk, None]:
        """
        Stream TTS audio chunks from Edge-TTS.

        Yields AudioChunk objects containing raw MP3 bytes.
        The first chunk typically arrives within 150-300ms.
        """
        async for item in self.stream_speech_with_boundaries(text, voice):
            if item["type"] == "audio":
                yield AudioChunk(
                    data=item["data"],
                    chunk_index=item["chunk_index"],
                    is_final=False,
                )
            elif item["type"] == "final":
                yield AudioChunk(data=b"", chunk_index=item["total_chunks"], is_final=True)
