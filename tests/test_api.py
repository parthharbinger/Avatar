"""
Integration tests for the REST API and WebSocket endpoints.
Uses httpx.AsyncClient with FastAPI's TestClient.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(autouse=True)
async def run_lifespan():
    """Trigger the app lifespan (starts session manager)."""
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "active_sessions" in data


@pytest.mark.asyncio
async def test_create_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert "ws_url" in data


@pytest.mark.asyncio
async def test_get_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/sessions")
        session_id = create_resp.json()["session_id"]
        get_resp = await client.get(f"/api/v1/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_delete_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/sessions")
        session_id = create_resp.json()["session_id"]
        delete_resp = await client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_get_nonexistent_session_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_providers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    provider_ids = [p["id"] for p in data["providers"]]
    assert "d-id" in provider_ids
    assert "anam" in provider_ids
    assert "simli" in provider_ids
    assert "akool" in provider_ids
    assert "heygen" in provider_ids
    assert "edge-tts" in provider_ids


@pytest.mark.asyncio
async def test_get_cost_assumptions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/costs")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "edge-tts" in data["providers"]
    assert "d-id" in data["providers"]
    assert "monthly_projection_presets" in data


@pytest.mark.asyncio
async def test_estimate_costs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/costs/estimate",
            json={"sessions_per_month": 5000, "avg_duration_minutes": 2.0, "active_engine": "edge-tts"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total_streaming_minutes"] == 10000
    assert "comparison_breakdown" in data
    assert "edge-tts" in data["comparison_breakdown"]


from app.config import settings


@pytest.mark.asyncio
async def test_profiles_crud_and_rag():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Obtain admin token
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.admin_default_email, "password": settings.admin_default_password},
        )
        admin_token = admin_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Create Profile
        create_resp = await client.post(
            "/api/v1/profiles",
            headers=headers,
            json={"name": "AI Expert Adam", "persona": "male", "system_prompt": "You are a test expert."}
        )
        assert create_resp.status_code == 201
        p_data = create_resp.json()
        profile_id = p_data["profile_id"]
        assert p_data["name"] == "AI Expert Adam"
        assert p_data["persona"] == "male"

        # 2. Get Profile
        get_resp = await client.get(f"/api/v1/profiles/{profile_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["profile_id"] == profile_id

        # 3. List Profiles
        list_resp = await client.get("/api/v1/profiles")
        assert list_resp.status_code == 200
        assert any(p["profile_id"] == profile_id for p in list_resp.json())

        # 4. Upload & Index a Document
        file_content = b"Apex Global Travel baggage policy allows one free carry-on up to 10kg."
        files = {"file": ("baggage_policy.txt", file_content, "text/plain")}
        doc_resp = await client.post(f"/api/v1/profiles/{profile_id}/documents", headers=headers, files=files)
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["status"] == "indexed"
        assert doc_data["profile"]["documents"][0]["filename"] == "baggage_policy.txt"

        # 5. Delete Profile
        del_resp = await client.delete(f"/api/v1/profiles/{profile_id}", headers=headers)
        assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_webrtc_interrupt_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a session
        sess_resp = await client.post("/api/v1/sessions")
        assert sess_resp.status_code == 201
        session_id = sess_resp.json()["session_id"]

        # Call interrupt endpoint
        interrupt_resp = await client.post(f"/api/v1/sessions/{session_id}/webrtc/interrupt?provider=edge-tts")
        assert interrupt_resp.status_code == 200


@pytest.mark.asyncio
async def test_logs_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Query logs
        logs_resp = await client.get("/api/v1/logs?limit=10")
        assert logs_resp.status_code == 200
        logs_data = logs_resp.json()
        assert "count" in logs_data
        assert "logs" in logs_data
        assert isinstance(logs_data["logs"], list)

        # 2. Query error logs
        err_resp = await client.get("/api/v1/logs/errors?limit=10")
        assert err_resp.status_code == 200
        err_data = err_resp.json()
        assert "count" in err_data
        assert "errors" in err_data
        assert isinstance(err_data["errors"], list)


