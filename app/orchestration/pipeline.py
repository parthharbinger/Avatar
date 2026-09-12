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
from app.viseme.mapper import map_text_to_visemes
from app.logging_config import get_logger

logger = get_logger(__name__)


async def run_speech_pipeline(
    websocket: WebSocket,
    text: str,
    speech_id: Optional[str] = None,
) -> None:
    """
    Full TTS → Viseme → Stream pipeline for one speech turn.

    Sends the following WebSocket JSON messages in order:
      1. {"type": "start", "speech_id": "..."}
      2. {"type": "viseme_timeline", "events": [...], "speech_id": "..."}
      3. {"type": "audio_chunk", "data": "<base64>", "chunk_index": N, "speech_id": "..."}
         (repeated for each chunk)
      4. {"type": "end", "speech_id": "..."} on success
         OR {"type": "interrupted", "speech_id": "..."} on cancellation

    Args:
        websocket: The active WebSocket connection.
        text: The text to speak.
        speech_id: Optional ID for this speech turn (auto-generated if not provided).
    """
    speech_id = speech_id or str(uuid.uuid4())
    tts = get_tts_adapter()

    logger.info(
        "Pipeline started",
        extra={"event": "pipeline_start", "speech_id": speech_id, "text_len": len(text)},
    )

    try:
        # 1. Signal start
        await websocket.send_json({"type": "start", "speech_id": speech_id})

        # 2. Pre-compute viseme timeline and send it ahead of audio
        #    The client receives this before any audio so it can pre-load the animation.
        viseme_events = map_text_to_visemes(text)
        await websocket.send_json({
            "type": "viseme_timeline",
            "speech_id": speech_id,
            "events": [e.to_dict() for e in viseme_events],
        })

        # 3. Stream audio chunks
        async for chunk in tts.stream_speech(text):
            if chunk.is_final:
                break
            # Encode binary audio as base64 for JSON transport
            encoded = base64.b64encode(chunk.data).decode("utf-8")
            await websocket.send_json({
                "type": "audio_chunk",
                "speech_id": speech_id,
                "chunk_index": chunk.chunk_index,
                "data": encoded,
            })

        # 4. Signal end
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
