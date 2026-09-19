"""
Authentication API Router.
Handles Registration, Login, Token Refresh, Profile View and Password Updates.
"""
import uuid
from fastapi import APIRouter, HTTPException, status, Depends

from app.db.database import db
from app.auth.models import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    UserUpdate,
    UserRole,
)
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.auth.dependencies import get_current_user
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(body: UserCreate):
    # Check if user already exists
    existing = await db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

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

    logger.info("User registered successfully", extra={"user_id": user_id, "email": body.email})
    return UserResponse(**user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login (returns JWT Access & Refresh tokens)",
)
async def login(body: LoginRequest):
    user = await db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    access_token, expires_in = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
    )
    refresh_token = create_refresh_token(user_id=user["id"])

    logger.info("User login successful", extra={"user_id": user["id"], "email": user["email"]})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse(**user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using a valid refresh token",
)
async def refresh_token_endpoint(body: RefreshTokenRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_id = payload.get("sub")
    user = await db.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    access_token, expires_in = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
    )
    new_refresh_token = create_refresh_token(user_id=user["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse(**user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    user = await db.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse(**user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user's profile info",
)
async def update_me(body: UserUpdate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    updates = {}

    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.email is not None:
        existing = await db.get_user_by_email(body.email)
        if existing and existing["id"] != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken.")
        updates["email"] = body.email

    # Standard users cannot elevate their own role or max_sessions
    if current_user.get("role") == UserRole.ADMIN:
        if body.role is not None:
            updates["role"] = body.role.value
        if body.allowed_engines is not None:
            updates["allowed_engines"] = body.allowed_engines
        if body.max_concurrent_sessions is not None:
            updates["max_concurrent_sessions"] = body.max_concurrent_sessions

    updated = await db.update_user(user_id, updates)
    return UserResponse(**updated)


@router.post(
    "/me/password",
    summary="Change current user's password",
)
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    user = await db.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not verify_password(body.old_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password.",
        )

    new_hashed = hash_password(body.new_password)
    await db.update_user(user["id"], {"hashed_password": new_hashed})
    return {"status": "password_updated"}
