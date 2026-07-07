from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.base import Base
from src.db.session import get_async_engine
from src.main import app


@pytest.fixture
async def api_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("src.db.session.get_session_factory", lambda eng=None: factory)
    monkeypatch.setattr("src.db.session.get_async_engine", lambda url=None: engine)
    get_async_engine.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


@pytest.mark.asyncio
async def test_live_status_stopped(api_client) -> None:
    client = api_client
    from src.runtime.live_manager import live_manager

    await live_manager.stop()
    resp = await client.get("/api/v1/live/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


@pytest.mark.asyncio
async def test_live_start_stop(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client = api_client
    from src.runtime.live_manager import live_manager

    await live_manager.stop()

    async def fake_start(**kwargs):
        live_manager._state.status = "running"  # noqa: SLF001
        live_manager._state.mode = kwargs.get("mode", "paper")  # noqa: SLF001
        return live_manager.status_dict()

    monkeypatch.setattr(live_manager, "start", fake_start)
    monkeypatch.setattr(live_manager, "stop", AsyncMock(return_value=live_manager.status_dict()))

    start = await client.post("/api/v1/live/start", json={"mode": "paper"})
    assert start.status_code == 200
    assert start.json()["status"] == "running"

    stop = await client.post("/api/v1/live/stop")
    assert stop.status_code == 200


@pytest.mark.asyncio
async def test_health_phase_7(api_client) -> None:
    client = api_client
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "7-live-adapters"
