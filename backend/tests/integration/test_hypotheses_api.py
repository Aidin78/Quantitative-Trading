from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.settings import get_settings
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
        yield client, factory
    await engine.dispose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_and_get_hypothesis(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.post(
        "/api/v1/hypotheses",
        headers=auth_headers,
        json={
            "observation": "Momentum performs poorly during high volatility.",
            "statement": "High volatility reduces the reliability of momentum signals.",
            "expected_effect": "Improve risk-adjusted return and reduce drawdown.",
            "proposed_change": "Disable momentum signals above the 80th volatility percentile.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    hypothesis_id = body["hypothesis_id"]

    get_resp = await client.get(f"/api/v1/hypotheses/{hypothesis_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["observation"].startswith("Momentum performs poorly")


@pytest.mark.asyncio
async def test_get_hypothesis_not_found(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/hypotheses/hyp_missing0000", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_hypotheses_empty(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/hypotheses", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_link_and_resolve_hypothesis(api_client, auth_headers) -> None:
    client, _ = api_client
    create_resp = await client.post(
        "/api/v1/hypotheses",
        headers=auth_headers,
        json={
            "observation": "o",
            "statement": "s",
            "expected_effect": "e",
            "proposed_change": "c",
        },
    )
    hypothesis_id = create_resp.json()["hypothesis_id"]

    link_resp = await client.post(
        f"/api/v1/hypotheses/{hypothesis_id}/link",
        headers=auth_headers,
        json={"experiment_id": "exp_test001"},
    )
    assert link_resp.status_code == 200
    assert link_resp.json()["status"] == "tested"
    assert link_resp.json()["tested_by_experiment_id"] == "exp_test001"

    resolve_resp = await client.post(
        f"/api/v1/hypotheses/{hypothesis_id}/resolve",
        headers=auth_headers,
        json={"confirmed": True},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_search_similar_hypotheses(api_client, auth_headers) -> None:
    client, _ = api_client
    await client.post(
        "/api/v1/hypotheses",
        headers=auth_headers,
        json={
            "observation": "o",
            "statement": "s",
            "expected_effect": "e",
            "proposed_change": "Disable momentum signals when volatility percentile exceeds 80",
        },
    )

    resp = await client.post(
        "/api/v1/hypotheses/search",
        headers=auth_headers,
        json={
            "proposed_change": "Reduce momentum exposure when volatility percentile is high",
            "min_overlap": 0.2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "momentum" in body["items"][0]["proposed_change"].lower()
