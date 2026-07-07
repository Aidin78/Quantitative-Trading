from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.settings import get_settings
from src.db.base import Base
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
async def test_health_public(api_client) -> None:
    client, _ = api_client
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "6-observability"


@pytest.mark.asyncio
async def test_decisions_public_without_auth(api_client) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/decisions")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_and_list_decisions(api_client, auth_headers) -> None:
    client, factory = api_client
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    from datetime import UTC, datetime

    from src.core.contracts.event import EventFamily
    from src.db.repositories.decision import persist_decision_from_event

    event = build_envelope(
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_MADE,
        event_time=datetime.now(UTC),
        processing_time=datetime.now(UTC),
        correlation_id="cycle_api_test",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_api_test",
            "result": "rejected",
            "state_snapshot_id": "snap_1",
            "decision_log": {
                "market_filter": {"passed": False, "reason": "low_volatility"},
                "provider_signals": [],
                "aggregation": {"method": "weighted_majority", "side": "HOLD", "confidence": 0.5},
                "risk_check": {"passed": True, "checks": [], "state_snapshot_id": "snap_1"},
                "state_snapshot_id": "snap_1",
                "portfolio_version": 1,
                "risk_state_version": 1,
            },
        },
    )
    reject_event = build_envelope(
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_REJECTED,
        event_time=datetime.now(UTC),
        processing_time=datetime.now(UTC),
        correlation_id="cycle_api_test",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_api_test",
            "state_snapshot_id": "snap_1",
            "rejection_stage": "market_filter",
            "rejection_reason": "low_volatility",
            "decision_log": event.payload["decision_log"],
        },
    )
    async with factory() as session:
        await persist_decision_from_event(session, event)
        from src.db.repositories.backtest import persist_event

        await persist_event(session, event)
        await persist_event(session, reject_event)
        await session.commit()

    resp = await client.get("/api/v1/decisions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["id"] == "dec_api_test" for item in data["items"])

    detail = await client.get("/api/v1/decisions/dec_api_test", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["rejection_stage"] == "market_filter"


@pytest.mark.asyncio
async def test_engine_config_get_patch(api_client) -> None:
    client, _ = api_client
    get_resp = await client.get("/api/v1/engine/config")
    assert get_resp.status_code == 200
    assert "engine" in get_resp.json()


@pytest.mark.asyncio
async def test_providers_list(api_client) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/providers")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 2
