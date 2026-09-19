"""
Cryptographic security utilities for Password Hashing, JWT Tokens, and API Keys.
"""
import os
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

import jwt

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

PBKDF2_ITERATIONS = 120_000
SALT_SIZE = 16


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256 with a secure random salt.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_bytes(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])

        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(expected_key, computed_key)
    except Exception as e:
        logger.error("Password verification error", extra={"error": str(e)})
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """
    Generate a signed JWT Access Token.
    Returns (token_str, expires_in_seconds).
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expires_in = settings.access_token_expire_minutes * 60
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_refresh_token(user_id: str) -> str:
    """
    Generate a signed JWT Refresh Token (30 days validity).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Decode and validate a signed JWT token.
    Returns decoded payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != expected_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token", extra={"error": str(e)})
        return None


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a high-entropy API key for SDK/programmatic access.
    Returns (plaintext_key, key_prefix, hashed_key).
    Example key: ak_live_3f9a8b1c...
    """
    raw_secret = secrets.token_hex(24)
    plaintext_key = f"ak_live_{raw_secret}"
    key_prefix = f"ak_live_{raw_secret[:6]}..."
    hashed_key = hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()
    return plaintext_key, key_prefix, hashed_key


def hash_api_key(api_key: str) -> str:
    """
    Hash an incoming API key to compare against database.
    """
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()
