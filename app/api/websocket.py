"""
WebSocket endpoint — the core real-time streaming handler.

Protocol:
  Client → Server (JSON):
    {"action": "speak", "text": "Hello world"}
    {"action": "interrupt"}
    {"action": "ping"}

  Server → Client (JSON):
    {"type": "connected", "session_id": "..."}
    {"type": "start", "speech_id": "..."}
    {"type": "viseme_timeline", "speech_id": "...", "events": [...]}
    {"type": "audio_chunk", "speech_id": "...", "chunk_index": N, "data": "<base64 MP3>"}
    {"type": "end", "speech_id": "..."}
    {"type": "interrupted", "speech_id": "..."}
    {"type": "error", "message": "..."}
    {"type": "pong"}
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.sessions.manager import session_manager, SessionNotFoundError
from app.sessions.models import SessionState
from app.orchestration.pipeline import run_speech_pipeline
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/api/v1/stream/{session_id}")
async def avatar_stream(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for real-time avatar streaming.

    Flow:
      1. Accept connection, verify session exists.
      2. Send 'connected' confirmation.
      3. Enter message loop — dispatch 'speak' and 'interrupt' actions.
      4. On disconnect, clean up session and cancel any active task.
    """
    # Verify session exists before accepting
    try:
        session = await session_manager.get_session(session_id)
    except SessionNotFoundError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await session_manager.update_state(session_id, SessionState.CONNECTED)
    await websocket.send_json({"type": "connected", "session_id": session_id})

    logger.info(
        "WebSocket connected",
        extra={"event": "ws_connected", "session_id": session_id},
    )

    active_task: Optional[asyncio.Task] = None

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action", "").lower()

            if action == "speak":
                text = message.get("text", "").strip()
                if not text:
                    await websocket.send_json({"type": "error", "message": "text field is required for speak action."})
                    continue

                # Cancel any currently running speech task (barge-in)
                if active_task and not active_task.done():
                    active_task.cancel()
                    try:
                        await active_task
                    except asyncio.CancelledError:
                        pass

                # Start a new speech pipeline as a cancellable background task
                await session_manager.update_state(session_id, SessionState.SPEAKING)
                active_task = asyncio.create_task(
                    run_speech_pipeline(websocket, text)
                )

                # Callback to update state when task completes naturally
                def on_task_done(task: asyncio.Task):
                    if not task.cancelled() and task.exception() is None:
                        asyncio.create_task(
                            session_manager.update_state(session_id, SessionState.IDLE)
                        )

                active_task.add_done_callback(on_task_done)

            elif action == "interrupt":
                if active_task and not active_task.done():
                    active_task.cancel()
                    try:
                        await active_task
                    except asyncio.CancelledError:
                        pass
                await session_manager.update_state(session_id, SessionState.IDLE)
                logger.info(
                    "Barge-in interrupt received",
                    extra={"event": "ws_interrupt", "session_id": session_id},
                )

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: '{action}'. Valid actions: speak, interrupt, ping.",
                })

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected",
            extra={"event": "ws_disconnected", "session_id": session_id},
        )
    except Exception as e:
        logger.error(
            "WebSocket error",
            extra={"event": "ws_error", "session_id": session_id, "error": str(e)},
        )
    finally:
        # Always cancel any running task and clean up session on disconnect
        if active_task and not active_task.done():
            active_task.cancel()
        await session_manager.update_state(session_id, SessionState.CLOSING)
        await session_manager.remove_session(session_id)
        logger.info(
            "Session cleaned up",
            extra={"event": "ws_cleanup", "session_id": session_id},
        )
