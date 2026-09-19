"""
Async SQLite Database service for User Management & API Keys.
Uses aiosqlite with WAL mode for fast concurrent operations.
"""
import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncGenerator
import aiosqlite

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.db_path
        self._lock = asyncio.Lock()

    def _ensure_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        self._ensure_dir()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn

    async def init_db(self):
        """Create tables and indexes if they do not exist."""
        self._ensure_dir()
        async with self.get_connection() as conn:
            # Users table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    allowed_engines TEXT NOT NULL DEFAULT '["canvas", "edge-tts"]',
                    max_concurrent_sessions INTEGER NOT NULL DEFAULT 5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

            # API Keys table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    hashed_key TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL DEFAULT 'developer',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    allowed_engines TEXT NOT NULL DEFAULT '["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"]',
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hashed ON api_keys(hashed_key)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")

            await conn.commit()
            logger.info("Auth database initialized", extra={"db_path": self.db_path})

    # ── User Queries ─────────────────────────────────────────────────────────

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if isinstance(data.get("allowed_engines"), str):
                try:
                    data["allowed_engines"] = json.loads(data["allowed_engines"])
                except Exception:
                    data["allowed_engines"] = ["canvas", "edge-tts"]
            return data

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if isinstance(data.get("allowed_engines"), str):
                try:
                    data["allowed_engines"] = json.loads(data["allowed_engines"])
                except Exception:
                    data["allowed_engines"] = ["canvas", "edge-tts"]
            return data

    async def list_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, email, full_name, role, is_active, allowed_engines, max_concurrent_sessions, created_at, updated_at "
                "FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
            users = []
            for row in rows:
                d = dict(row)
                if isinstance(d.get("allowed_engines"), str):
                    try:
                        d["allowed_engines"] = json.loads(d["allowed_engines"])
                    except Exception:
                        d["allowed_engines"] = ["canvas", "edge-tts"]
                users.append(d)
            return users

    async def create_user(
        self,
        user_id: str,
        email: str,
        hashed_password: str,
        full_name: str,
        role: str = "user",
        is_active: bool = True,
        allowed_engines: Optional[List[str]] = None,
        max_concurrent_sessions: int = 5,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        engines = allowed_engines or (
            ["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"]
            if role in ("admin", "developer")
            else ["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"]
        )
        engines_json = json.dumps(engines)

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, allowed_engines, max_concurrent_sessions, created_at, updated_at)
                VALUES (?, LOWER(?), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    email,
                    hashed_password,
                    full_name,
                    role,
                    1 if is_active else 0,
                    engines_json,
                    max_concurrent_sessions,
                    now,
                    now,
                ),
            )
            await conn.commit()

        return {
            "id": user_id,
            "email": email.lower(),
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
            "allowed_engines": engines,
            "max_concurrent_sessions": max_concurrent_sessions,
            "created_at": now,
            "updated_at": now,
        }

    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fields = []
        values = []
        for key, val in updates.items():
            if key == "allowed_engines" and isinstance(val, list):
                fields.append("allowed_engines = ?")
                values.append(json.dumps(val))
            elif key == "is_active":
                fields.append("is_active = ?")
                values.append(1 if val else 0)
            elif key == "email":
                fields.append("email = LOWER(?)")
                values.append(val)
            elif key in ("full_name", "hashed_password", "role", "max_concurrent_sessions"):
                fields.append(f"{key} = ?")
                values.append(val)

        if not fields:
            return await self.get_user_by_id(user_id)

        now = datetime.now(timezone.utc).isoformat()
        fields.append("updated_at = ?")
        values.append(now)
        values.append(user_id)

        async with self.get_connection() as conn:
            await conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
            await conn.commit()

        return await self.get_user_by_id(user_id)

    async def delete_user(self, user_id: str) -> bool:
        async with self.get_connection() as conn:
            cursor = await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await conn.commit()
            return cursor.rowcount > 0

    async def count_users(self) -> int:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ── API Key Queries ──────────────────────────────────────────────────────

    async def create_api_key(
        self,
        key_id: str,
        user_id: str,
        name: str,
        key_prefix: str,
        hashed_key: str,
        role: str = "developer",
        allowed_engines: Optional[List[str]] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        engines = allowed_engines or ["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"]
        engines_json = json.dumps(engines)

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO api_keys (id, user_id, name, key_prefix, hashed_key, role, is_active, allowed_engines, expires_at, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, NULL)
                """,
                (
                    key_id,
                    user_id,
                    name,
                    key_prefix,
                    hashed_key,
                    role,
                    engines_json,
                    expires_at,
                    now,
                ),
            )
            await conn.commit()

        return {
            "id": key_id,
            "user_id": user_id,
            "name": name,
            "key_prefix": key_prefix,
            "role": role,
            "is_active": True,
            "allowed_engines": engines,
            "expires_at": expires_at,
            "created_at": now,
            "last_used_at": None,
        }

    async def get_api_key_by_hash(self, hashed_key: str) -> Optional[Dict[str, Any]]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT ak.*, u.email as user_email, u.full_name as user_full_name, u.is_active as user_active
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.hashed_key = ? AND ak.is_active = 1 AND u.is_active = 1
                """,
                (hashed_key,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if isinstance(data.get("allowed_engines"), str):
                try:
                    data["allowed_engines"] = json.loads(data["allowed_engines"])
                except Exception:
                    data["allowed_engines"] = ["canvas", "edge-tts"]
            return data

    async def update_api_key_last_used(self, key_id: str):
        now = datetime.now(timezone.utc).isoformat()
        async with self.get_connection() as conn:
            await conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, key_id))
            await conn.commit()

    async def list_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, user_id, name, key_prefix, role, is_active, allowed_engines, expires_at, created_at, last_used_at
                FROM api_keys WHERE user_id = ? ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            keys = []
            for row in rows:
                d = dict(row)
                if isinstance(d.get("allowed_engines"), str):
                    try:
                        d["allowed_engines"] = json.loads(d["allowed_engines"])
                    except Exception:
                        d["allowed_engines"] = []
                keys.append(d)
            return keys

    async def delete_api_key(self, key_id: str, user_id: Optional[str] = None) -> bool:
        async with self.get_connection() as conn:
            if user_id:
                cursor = await conn.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
            else:
                cursor = await conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
            await conn.commit()
            return cursor.rowcount > 0


# Global singleton
db = Database()
