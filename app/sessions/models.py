"""
Session data models and state machine enum.
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionState(str, Enum):
    CREATED = "CREATED"
    CONNECTED = "CONNECTED"
    IDLE = "IDLE"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.CREATED
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    avatar_id: str = "default"
    active_speech_id: Optional[str] = None

    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active_at = time.time()

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has been idle past the timeout threshold."""
        return (time.time() - self.last_active_at) > timeout_seconds

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "avatar_id": self.avatar_id,
        }
