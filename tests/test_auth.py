"""
Automated tests for Authentication (Registration, Login, JWT, Refresh, Password).
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.auth.security import hash_password, verify_password, create_access_token, decode_token


@pytest.fixture(autouse=True)
async def run_lifespan():
    async with app.router.lifespan_context(app):
        yield


def test_password_hashing_and_verification():
    raw = "SuperSecretPassword123!"
    hashed = hash_password(raw)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_generation_and_decoding():
    token, expires_in = create_access_token("user-123", "user@test.com", "developer")
    assert isinstance(token, str)
    assert expires_in > 0

    decoded = decode_token(token, expected_type="access")
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "user@test.com"
    assert decoded["role"] == "developer"


@pytest.mark.asyncio
async def test_admin_default_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.admin_default_email, "password": settings.admin_default_password},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_user_registration_and_login_flow():
    import uuid
    test_email = f"sarah.{uuid.uuid4().hex[:8]}@avatar.ai"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register new user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "Password123!",
                "full_name": "Sarah Connor",
                "role": "developer",
            },
        )
        assert reg_resp.status_code == 201
        user_data = reg_resp.json()
        assert user_data["email"] == test_email
        assert user_data["full_name"] == "Sarah Connor"
        assert user_data["role"] == "developer"

        # 2. Duplicate registration fails (409 Conflict)
        dup_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "Password123!",
                "full_name": "Duplicate Sarah",
            },
        )
        assert dup_resp.status_code == 409

        # 3. Login with registered user
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "Password123!"},
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]

        # 4. Access /auth/me with Bearer Token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == test_email

        # 5. Refresh token
        ref_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert ref_resp.status_code == 200
        assert "access_token" in ref_resp.json()

        # 6. Change Password
        pw_resp = await client.post(
            "/api/v1/auth/me/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": "Password123!", "new_password": "NewSuperPassword456!"},
        )
        assert pw_resp.status_code == 200
        assert pw_resp.json()["status"] == "password_updated"

        # 7. Old password no longer works
        fail_login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "Password123!"},
        )
        assert fail_login.status_code == 401

        # 8. New password works
        new_login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "NewSuperPassword456!"},
        )
        assert new_login.status_code == 200
