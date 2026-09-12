"""
Edge-TTS adapter — streams MP3 audio chunks from Microsoft's free neural TTS.
No API key required. Uses the edge-tts Python library.
"""
import asyncio
import ssl
from typing import AsyncGenerator

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

    async def stream_speech(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """
        Stream TTS audio chunks from Edge-TTS.

        Yields AudioChunk objects containing raw MP3 bytes.
        The first chunk typically arrives within 150-300ms.
        """
        logger.info(
            "EdgeTTS stream_speech called",
            extra={"event": "tts_start", "provider": "edge-tts", "text_len": len(text)},
        )

        ssl_param = False if not settings.edge_tts_verify_ssl else None
        connector = aiohttp.TCPConnector(ssl=ssl_param)
        chunk_index = 0

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self._voice,
                connector=connector,
            )

            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    yield AudioChunk(
                        data=chunk["data"],
                        chunk_index=chunk_index,
                        is_final=False,
                    )
                    chunk_index += 1

            # Yield a final empty chunk to signal stream completion
            yield AudioChunk(data=b"", chunk_index=chunk_index, is_final=True)
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
