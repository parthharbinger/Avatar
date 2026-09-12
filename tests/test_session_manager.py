"""
Unit tests for InMemorySessionManager.
"""
import asyncio
import pytest
from app.sessions.manager import InMemorySessionManager, SessionNotFoundError, SessionLimitExceededError
from app.sessions.models import SessionState


@pytest.fixture
async def manager():
    m = InMemorySessionManager()
    await m.start()
    yield m
    await m.stop()


@pytest.mark.asyncio
async def test_create_session(manager):
    session = await manager.create_session()
    assert session.session_id is not None
    assert session.state == SessionState.CREATED


@pytest.mark.asyncio
async def test_get_session(manager):
    session = await manager.create_session()
    retrieved = await manager.get_session(session.session_id)
    assert retrieved.session_id == session.session_id


@pytest.mark.asyncio
async def test_get_nonexistent_session_raises(manager):
    with pytest.raises(SessionNotFoundError):
        await manager.get_session("nonexistent-id")


@pytest.mark.asyncio
async def test_update_state(manager):
    session = await manager.create_session()
    await manager.update_state(session.session_id, SessionState.CONNECTED)
    updated = await manager.get_session(session.session_id)
    assert updated.state == SessionState.CONNECTED


@pytest.mark.asyncio
async def test_remove_session(manager):
    session = await manager.create_session()
    await manager.remove_session(session.session_id)
    with pytest.raises(SessionNotFoundError):
        await manager.get_session(session.session_id)


@pytest.mark.asyncio
async def test_session_limit_exceeded():
    m = InMemorySessionManager()
    m._sessions = {}  # Start clean
    # Temporarily override max
    from app import config
    original = config.settings.max_concurrent_sessions
    config.settings.max_concurrent_sessions = 2

    await m.create_session()
    await m.create_session()
    with pytest.raises(SessionLimitExceededError):
        await m.create_session()

    config.settings.max_concurrent_sessions = original


@pytest.mark.asyncio
async def test_get_active_count(manager):
    count_before = await manager.get_active_count()
    await manager.create_session()
    await manager.create_session()
    count_after = await manager.get_active_count()
    assert count_after == count_before + 2
