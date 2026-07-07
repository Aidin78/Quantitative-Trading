from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.contracts.event import EventFamily
from src.core.settings import get_settings
from src.db.base import Base
from src.db.repositories.decision import persist_decision_from_event
from src.db.session import get_async_engine
from src.events.envelopes import DecisionEventType, build_envelope
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
        yield client, factory
    await engine.dispose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_analytics_overview_empty(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/analytics/overview?period=30d", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "30d"
    assert body["total_decisions"] == 0
    assert body["approval_rate"] == 0.0


@pytest.mark.asyncio
async def test_analytics_overview_with_decisions(api_client, auth_headers) -> None:
    client, factory = api_client
    now = datetime.now(UTC)
    event = build_envelope(
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_MADE,
        event_time=now,
        processing_time=now,
        correlation_id="cycle_analytics",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_analytics",
            "result": "approved",
            "state_snapshot_id": "snap_1",
            "decision_log": {
                "market_filter": {"passed": True},
                "provider_signals": [{"provider_id": "ema_crossover"}],
                "aggregation": {"method": "majority", "side": "BUY", "confidence": 0.8},
                "risk_check": {"passed": True, "checks": [], "state_snapshot_id": "snap_1"},
                "state_snapshot_id": "snap_1",
                "portfolio_version": 1,
                "risk_state_version": 1,
            },
        },
    )
    async with factory() as session:
        await persist_decision_from_event(session, event)
        await session.commit()

    resp = await client.get("/api/v1/analytics/overview?period=30d", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_decisions"] >= 1
    assert body["approval_rate"] > 0
    assert any(p["provider_id"] == "ema_crossover" for p in body["provider_contribution"])


@pytest.mark.asyncio
async def test_analytics_heatmap(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/analytics/heatmap?period=7d", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "7d"
    assert "data" in body


@pytest.mark.asyncio
async def test_metrics_endpoint(api_client) -> None:
    client, _ = api_client
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "qtp_decisions_total" in resp.text
