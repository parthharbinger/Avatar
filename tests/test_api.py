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
