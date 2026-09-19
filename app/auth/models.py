"""
Pydantic models and schemas for User Management, Authentication & API Keys.
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    USER = "user"


# Role hierarchy score for permission comparison
ROLE_HIERARCHY = {
    UserRole.ADMIN: 30,
    UserRole.DEVELOPER: 20,
    UserRole.USER: 10,
}


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")
    role: Optional[UserRole] = UserRole.USER
    allowed_engines: Optional[List[str]] = Field(
        default=["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"],
        description="List of allowed avatar rendering engines for this user.",
    )
    max_concurrent_sessions: Optional[int] = Field(default=5, ge=1, le=50)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    allowed_engines: Optional[List[str]] = None
    max_concurrent_sessions: Optional[int] = Field(None, ge=1, le=50)
    password: Optional[str] = Field(None, min_length=6)


class UserResponse(UserBase):
    id: str
    role: UserRole
    is_active: bool
    allowed_engines: List[str]
    max_concurrent_sessions: int
    created_at: str
    updated_at: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Friendly label for this API key")
    role: Optional[UserRole] = UserRole.DEVELOPER
    allowed_engines: Optional[List[str]] = Field(
        default=["canvas", "edge-tts", "d-id", "simli", "anam", "akool", "heygen"]
    )
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    role: UserRole
    is_active: bool
    allowed_engines: List[str]
    expires_at: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None
    api_key: Optional[str] = Field(None, description="Plaintext API Key — only returned once upon creation")
