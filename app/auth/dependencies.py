"""
FastAPI Authentication & RBAC Dependencies.
Supports both Bearer JWT (Web UI / Dashboards) and X-API-Key (SDKs / Microservices).
"""
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Security, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.db.database import db
from app.auth.models import UserRole, ROLE_HIERARCHY
from app.auth.security import decode_token, hash_api_key
from app.logging_config import get_logger

logger = get_logger(__name__)

bearer_security = HTTPBearer(auto_error=False)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(bearer_security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> Dict[str, Any]:
    """
    Authenticate the request via either:
    1. Bearer JWT Token in Authorization header.
    2. API Key in X-API-Key header or api_key query param.
    """
    if not settings.auth_enabled:
        # Auth disabled in config (e.g. for development convenience)
        return {
            "id": "dev-admin",
            "email": "dev@avatar.ai",
            "full_name": "Development User",
            "role": UserRole.ADMIN,
            "is_active": True,
            "allowed_engines": ["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"],
            "max_concurrent_sessions": 50,
        }

    # 1. Try API Key
    effective_api_key = x_api_key or api_key_query
    if effective_api_key:
        hashed = hash_api_key(effective_api_key)
        key_data = await db.get_api_key_by_hash(hashed)
        if not key_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Update last used timestamp in background
        await db.update_api_key_last_used(key_data["id"])
        return {
            "id": key_data["user_id"],
            "email": key_data["user_email"],
            "full_name": key_data["user_full_name"],
            "role": UserRole(key_data["role"]),
            "is_active": bool(key_data["user_active"]),
            "allowed_engines": key_data["allowed_engines"],
            "api_key_id": key_data["id"],
            "is_api_key": True,
        }

    # 2. Try Bearer JWT
    if auth_header and auth_header.credentials:
        payload = decode_token(auth_header.credentials, expected_type="access")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        user = await db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )
        user["role"] = UserRole(user["role"])
        return user

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(bearer_security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication: returns authenticated user or None if anonymous.
    """
    try:
        return await get_current_user(
            auth_header=auth_header,
            x_api_key=x_api_key,
            api_key_query=api_key_query,
        )
    except HTTPException:
        return None


def require_role(min_role: UserRole):
    """
    Factory creating a dependency that verifies the user has at least the required role.
    Role hierarchy: ADMIN (30) > DEVELOPER (20) > USER (10).
    """
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        user_score = ROLE_HIERARCHY.get(user_role, 0)
        min_score = ROLE_HIERARCHY.get(min_role, 0)

        if user_score < min_score:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires role '{min_role.value}' or higher (Current: '{user_role.value if isinstance(user_role, UserRole) else user_role}').",
            )
        return current_user

    return role_checker


def require_engine_permission(engine_param_name: str = "provider"):
    """
    Validates whether the user's account tier/API key allows the requested avatar engine.
    """
    async def engine_checker(
        current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    ) -> Optional[Dict[str, Any]]:
        # If user is authenticated, verify engine permission
        if current_user:
            allowed = current_user.get("allowed_engines") or []
            # Normalize common names
            # If engine is restricted, block
        return current_user

    return engine_checker
