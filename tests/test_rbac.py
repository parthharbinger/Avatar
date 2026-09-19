"""
Automated tests for Role-Based Access Control (RBAC) and engine permission restrictions.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings


@pytest.fixture(autouse=True)
async def run_lifespan():
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_rbac_admin_vs_developer_vs_user_roles():
    import uuid
    user_email = f"user.{uuid.uuid4().hex[:6]}@avatar.ai"
    dev_email = f"dev.{uuid.uuid4().hex[:6]}@avatar.ai"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login Admin
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.admin_default_email, "password": settings.admin_default_password},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        # 2. Register a standard user
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": user_email,
                "password": "UserPass123!",
                "full_name": "Standard User",
                "role": "user",
            },
        )
        user_login = await client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": "UserPass123!"},
        )
        user_token = user_login.json()["access_token"]

        # 3. Register a developer
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": dev_email,
                "password": "DevPass123!",
                "full_name": "Dev Engineer",
                "role": "developer",
            },
        )
        dev_login = await client.post(
            "/api/v1/auth/login",
            json={"email": dev_email, "password": "DevPass123!"},
        )
        dev_token = dev_login.json()["access_token"]

        # 4. Admin CAN list all users
        admin_users_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_users_resp.status_code == 200
        assert len(admin_users_resp.json()) >= 3

        # 5. Developer CANNOT list all users (403 Forbidden)
        dev_users_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {dev_token}"},
        )
        assert dev_users_resp.status_code == 403

        # 6. Standard User CANNOT list all users (403 Forbidden)
        user_users_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert user_users_resp.status_code == 403

        # 7. Developer CAN create RAG profile
        dev_prof_resp = await client.post(
            "/api/v1/profiles",
            headers={"Authorization": f"Bearer {dev_token}"},
            json={"name": "Dev Created Profile", "persona": "female"},
        )
        assert dev_prof_resp.status_code == 201
        created_pid = dev_prof_resp.json()["profile_id"]

        # 8. Standard User CANNOT create RAG profile (403 Forbidden)
        user_prof_resp = await client.post(
            "/api/v1/profiles",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"name": "User Profile", "persona": "male"},
        )
        assert user_prof_resp.status_code == 403

        # 9. Clean up test profile
        del_prof_resp = await client.delete(
            f"/api/v1/profiles/{created_pid}",
            headers={"Authorization": f"Bearer {dev_token}"},
        )
        assert del_prof_resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_user_crud_and_engine_permission_gate():
    import uuid
    free_email = f"free.{uuid.uuid4().hex[:6]}@avatar.ai"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Admin login
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.admin_default_email, "password": settings.admin_default_password},
        )
        admin_token = admin_login.json()["access_token"]

        # 2. Admin provisions restricted user (only canvas allowed, no WebRTC)
        create_user_resp = await client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": free_email,
                "password": "FreeUser123!",
                "full_name": "Free Tier User",
                "role": "user",
                "allowed_engines": ["canvas", "edge-tts"],
                "max_concurrent_sessions": 2,
            },
        )
        assert create_user_resp.status_code == 201
        created_id = create_user_resp.json()["id"]

        # 3. Login as free tier user
        free_login = await client.post(
            "/api/v1/auth/login",
            json={"email": free_email, "password": "FreeUser123!"},
        )
        free_token = free_login.json()["access_token"]

        # 4. Attempt to create session and request HeyGen WebRTC stream (should be blocked with 403)
        sess_resp = await client.post(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {free_token}"},
        )
        assert sess_resp.status_code == 201
        sess_id = sess_resp.json()["session_id"]

        webrtc_offer_resp = await client.post(
            f"/api/v1/sessions/{sess_id}/webrtc/offer?provider=heygen",
            headers={"Authorization": f"Bearer {free_token}"},
        )
        assert webrtc_offer_resp.status_code == 403
        assert "not permitted for your user account tier" in webrtc_offer_resp.json()["detail"]

        # 5. Admin updates user to grant "heygen"
        update_resp = await client.put(
            f"/api/v1/users/{created_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"allowed_engines": ["canvas", "edge-tts", "heygen"]},
        )
        assert update_resp.status_code == 200
        assert "heygen" in update_resp.json()["allowed_engines"]
