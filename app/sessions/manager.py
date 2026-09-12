"""
In-memory session manager with TTL-based cleanup.
Designed with a pluggable interface — swap InMemorySessionManager
for RedisSessionManager when scaling horizontally.
"""
import asyncio
import logging
from typing import Dict, Optional

from app.sessions.models import Session, SessionState
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class SessionNotFoundError(Exception):
    pass


class SessionLimitExceededError(Exception):
    pass


class InMemorySessionManager:
    """
    Thread-safe in-memory session store.
    Runs a background cleanup task to expire idle sessions.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background cleanup loop. Call on app startup."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started", extra={"event": "session_manager_start"})

    async def stop(self) -> None:
        """Stop the cleanup loop. Call on app shutdown."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Session manager stopped", extra={"event": "session_manager_stop"})

    async def create_session(self, avatar_id: str = "default") -> Session:
        """Create and register a new session."""
        async with self._lock:
            if len(self._sessions) >= settings.max_concurrent_sessions:
                raise SessionLimitExceededError(
                    f"Maximum concurrent sessions ({settings.max_concurrent_sessions}) reached."
                )
            session = Session(avatar_id=avatar_id)
            self._sessions[session.session_id] = session
            logger.info(
                "Session created",
                extra={"event": "session_created", "session_id": session.session_id},
            )
            return session

    async def get_session(self, session_id: str) -> Session:
        """Retrieve an existing session by ID."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")
            session.touch()
            return session

    async def update_state(self, session_id: str, state: SessionState) -> None:
        """Transition a session to a new state."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")
            old_state = session.state
            session.state = state
            session.touch()
            logger.info(
                "Session state changed",
                extra={
                    "event": "session_state_change",
                    "session_id": session_id,
                    "from": old_state.value,
                    "to": state.value,
                },
            )

    async def remove_session(self, session_id: str) -> None:
        """Explicitly remove a session (on disconnect or DELETE request)."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(
                    "Session removed",
                    extra={"event": "session_removed", "session_id": session_id},
                )

    async def get_active_count(self) -> int:
        async with self._lock:
            return len(self._sessions)

    async def _cleanup_loop(self) -> None:
        """Periodically remove expired idle sessions."""
        while True:
            await asyncio.sleep(60)  # Check every 60 seconds
            async with self._lock:
                expired = [
                    sid
                    for sid, s in self._sessions.items()
                    if s.is_expired(settings.session_timeout_seconds)
                ]
                for sid in expired:
                    del self._sessions[sid]
                    logger.info(
                        "Session expired (TTL)",
                        extra={"event": "session_expired", "session_id": sid},
                    )


# Global singleton — imported by API routers and WebSocket handler
session_manager = InMemorySessionManager()
