"""
Stream orchestration pipeline.

Sequences: TTS streaming → Viseme mapping → WebSocket event emission.

Each pipeline run is an asyncio.Task so it can be cancelled mid-stream
for barge-in / interruption support.
"""
import asyncio
import base64
import uuid
from typing import Optional

from fastapi import WebSocket

from app.tts import get_tts_adapter
from app.viseme.mapper import map_text_to_visemes, from_word_boundaries
from app.logging_config import get_logger
from app.services.text_sanitizer import clean_text_for_speech

logger = get_logger(__name__)


async def run_speech_pipeline(
    websocket: WebSocket,
    text: str,
    speech_id: Optional[str] = None,
    voice: Optional[str] = None,
) -> None:
    """
    Full TTS → Viseme → Stream pipeline for one speech turn.
    """
    speech_id = speech_id or str(uuid.uuid4())
    text = clean_text_for_speech(text)
    tts = get_tts_adapter()

    logger.info(
        "Pipeline started",
        extra={"event": "pipeline_start", "speech_id": speech_id, "text_len": len(text), "voice": voice},
    )

    try:
        # 1. Signal start
        await websocket.send_json({"type": "start", "speech_id": speech_id})

        # 2. Check if adapter supports streaming with WordBoundaries (EdgeTTS)
        if hasattr(tts, "stream_speech_with_boundaries"):
            word_boundaries = []
            async for item in tts.stream_speech_with_boundaries(text, voice=voice):
                item_type = item["type"]
                if item_type == "word_boundary":
                    word_boundaries.append((item["word"], item["offset_ms"], item["duration_ms"]))
                elif item_type == "audio":
                    encoded = base64.b64encode(item["data"]).decode("utf-8")
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "speech_id": speech_id,
                        "chunk_index": item["chunk_index"],
                        "data": encoded,
                    })

            # Emit exact viseme timeline computed from audio word boundaries
            viseme_events = from_word_boundaries(word_boundaries)
            await websocket.send_json({
                "type": "viseme_timeline",
                "speech_id": speech_id,
                "events": [e.to_dict() for e in viseme_events],
            })
        else:
            # Fallback for generic TTS
            viseme_events = map_text_to_visemes(text)
            await websocket.send_json({
                "type": "viseme_timeline",
                "speech_id": speech_id,
                "events": [e.to_dict() for e in viseme_events],
            })
            async for chunk in tts.stream_speech(text):
                if chunk.is_final:
                    break
                encoded = base64.b64encode(chunk.data).decode("utf-8")
                await websocket.send_json({
                    "type": "audio_chunk",
                    "speech_id": speech_id,
                    "chunk_index": chunk.chunk_index,
                    "data": encoded,
                })

        # 3. Signal end
        await websocket.send_json({"type": "end", "speech_id": speech_id})
        logger.info(
            "Pipeline complete",
            extra={"event": "pipeline_end", "speech_id": speech_id},
        )

    except asyncio.CancelledError:
        # Barge-in: pipeline was cancelled by the interrupt handler
        logger.info(
            "Pipeline interrupted",
            extra={"event": "pipeline_interrupted", "speech_id": speech_id},
        )
        try:
            await websocket.send_json({"type": "interrupted", "speech_id": speech_id})
        except Exception:
            pass  # WebSocket may already be closing
        raise  # Re-raise so asyncio cleans up the task properly

    except Exception as e:
        logger.error(
            "Pipeline error",
            extra={"event": "pipeline_error", "speech_id": speech_id, "error": str(e)},
        )
        try:
            await websocket.send_json({
                "type": "error",
                "speech_id": speech_id,
                "message": "An internal error occurred during speech generation.",
            })
        except Exception:
            pass
