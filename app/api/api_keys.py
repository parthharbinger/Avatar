"""
API Keys Management Router.
Allows Developers and Admins to generate, list, and revoke API keys for the SDK.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from app.db.database import db
from app.auth.models import ApiKeyCreate, ApiKeyResponse, UserRole
from app.auth.security import generate_api_key
from app.auth.dependencies import get_current_user, require_role
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.get(
    "",
    response_model=List[ApiKeyResponse],
    summary="List all API keys belonging to the current user",
)
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    keys = await db.list_user_api_keys(current_user["id"])
    return [ApiKeyResponse(**k) for k in keys]


@router.post(
    "",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key for the SDK or background service",
)
async def create_api_key(
    body: ApiKeyCreate,
    current_user: dict = Depends(require_role(UserRole.DEVELOPER)),
):
    plaintext_key, key_prefix, hashed_key = generate_api_key()
    key_id = str(uuid.uuid4())

    expires_at = None
    if body.expires_in_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)).isoformat()

    # If the user is not admin, role cannot exceed their own role
    target_role = body.role.value if body.role else "developer"
    if current_user["role"] != UserRole.ADMIN and target_role == "admin":
        target_role = "developer"

    key_record = await db.create_api_key(
        key_id=key_id,
        user_id=current_user["id"],
        name=body.name,
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        role=target_role,
        allowed_engines=body.allowed_engines or current_user.get("allowed_engines"),
        expires_at=expires_at,
    )

    # Return plaintext key ONLY on creation response
    key_record["api_key"] = plaintext_key
    logger.info("Created new API key", extra={"user_id": current_user["id"], "key_id": key_id, "key_name": body.name})
    return ApiKeyResponse(**key_record)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    is_admin = current_user.get("role") == UserRole.ADMIN
    user_id_filter = None if is_admin else current_user["id"]

    deleted = await db.delete_api_key(key_id=key_id, user_id=user_id_filter)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    logger.info("Revoked API key", extra={"key_id": key_id, "user_id": current_user["id"]})
