"""
Automated tests for SDK API Key lifecycle, authentication with X-API-Key, and revocation.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.auth.security import generate_api_key, hash_api_key


@pytest.fixture(autouse=True)
async def run_lifespan():
    async with app.router.lifespan_context(app):
        yield


def test_api_key_crypto_generation():
    key, prefix, hashed = generate_api_key()
    assert key.startswith("ak_live_")
    assert prefix.startswith("ak_live_")
    assert len(hashed) == 64
    assert hash_api_key(key) == hashed


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_sdk_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login Admin
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.admin_default_email, "password": settings.admin_default_password},
        )
        admin_token = admin_login.json()["access_token"]

        # 2. Create an API Key for SDK embedding
        create_key_resp = await client.post(
            "/api/v1/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Production Next.js Web Widget",
                "role": "developer",
                "allowed_engines": ["canvas", "edge-tts", "simli", "anam"],
                "expires_in_days": 90,
            },
        )
        assert create_key_resp.status_code == 201
        key_data = create_key_resp.json()
        assert "api_key" in key_data
        api_key_str = key_data["api_key"]
        key_id = key_data["id"]
        assert api_key_str.startswith("ak_live_")

        # 3. List API keys
        list_keys_resp = await client.get(
            "/api/v1/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_keys_resp.status_code == 200
        assert any(k["id"] == key_id for k in list_keys_resp.json())

        # 4. Authenticate using X-API-Key header (as the SDK would)
        me_with_key = await client.get(
            "/api/v1/auth/me",
            headers={"X-API-Key": api_key_str},
        )
        assert me_with_key.status_code == 200
        assert me_with_key.json()["email"] == settings.admin_default_email

        # 5. Create a session using X-API-Key header
        sess_resp = await client.post(
            "/api/v1/sessions",
            headers={"X-API-Key": api_key_str},
        )
        assert sess_resp.status_code == 201
        assert "session_id" in sess_resp.json()

        # 6. Revoke / Delete the API key
        del_key_resp = await client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_key_resp.status_code == 204

        # 7. Using the revoked key now fails (401 Unauthorized)
        revoked_call = await client.get(
            "/api/v1/auth/me",
            headers={"X-API-Key": api_key_str},
        )
        assert revoked_call.status_code == 401
