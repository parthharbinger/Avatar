"""
User Management API Router (Admin & Management operations).
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db.database import db
from app.auth.models import UserRole, UserResponse, UserCreate, UserUpdate
from app.auth.security import hash_password
from app.auth.dependencies import get_current_user, require_role
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["User Management"])


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users (Admin only)",
)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    users = await db.list_users(limit=limit, offset=offset)
    return [UserResponse(**u) for u in users]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user with custom role and engine quotas (Admin only)",
)
async def create_user_admin(
    body: UserCreate,
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    existing = await db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(body.password)

    user = await db.create_user(
        user_id=user_id,
        email=body.email,
        hashed_password=hashed_pw,
        full_name=body.full_name,
        role=body.role.value if body.role else "user",
        is_active=True,
        allowed_engines=body.allowed_engines,
        max_concurrent_sessions=body.max_concurrent_sessions or 5,
    )
    return UserResponse(**user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details by ID (Admin or Self)",
)
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != UserRole.ADMIN and current_user["id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse(**user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user profile, role, or permissions (Admin only)",
)
async def update_user_admin(
    user_id: str,
    body: UserUpdate,
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updates = {}
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.email is not None:
        existing = await db.get_user_by_email(body.email)
        if existing and existing["id"] != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken.")
        updates["email"] = body.email
    if body.role is not None:
        updates["role"] = body.role.value
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.allowed_engines is not None:
        updates["allowed_engines"] = body.allowed_engines
    if body.max_concurrent_sessions is not None:
        updates["max_concurrent_sessions"] = body.max_concurrent_sessions
    if body.password is not None:
        updates["hashed_password"] = hash_password(body.password)

    updated = await db.update_user(user_id, updates)
    return UserResponse(**updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user (Admin only)",
)
async def delete_user_admin(
    user_id: str,
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    if admin["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own account.",
        )

    deleted = await db.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
