from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.settings import get_settings
from src.db.base import Base
from src.db.models import BacktestRunRow
from src.db.session import get_async_engine
from src.governance.hypothesis_generator import HypothesisDraft
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


@pytest.mark.asyncio
async def test_generate_hypothesis_job_completes_and_persists(api_client, auth_headers) -> None:
    client, factory = api_client
    async with factory() as session:
        session.add(
            BacktestRunRow(
                run_id="run_with_failures",
                symbol="BTC/USDT",
                timeframe="1h",
                config={},
                metrics={
                    "outcome": {
                        "failure_summary": {
                            "total_losses": 10,
                            "loss_share_by_regime": {"UP_HIGH": 1.0},
                            "low_confidence_loss_share": 0.5,
                            "avg_win": 40.0,
                            "avg_loss": -30.0,
                            "unattributed_trades": 0,
                        }
                    }
                },
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()

    draft = HypothesisDraft(
        observation="100% of losses occurred during UP_HIGH regime.",
        statement="Momentum signals degrade in high volatility.",
        expected_effect="Reduce drawdown in UP_HIGH regime.",
        proposed_change="Disable momentum signals above the 80th volatility percentile.",
    )
    with patch(
        "src.governance.hypothesis_generator.draft_hypothesis_from_failure_summary",
        return_value=draft,
    ):
        start_resp = await client.post(
            "/api/v1/hypotheses/generate",
            headers=auth_headers,
            json={"run_id": "run_with_failures"},
        )
        assert start_resp.status_code == 200
        job_id = start_resp.json()["job_id"]

        for _ in range(50):
            status_resp = await client.get(
                f"/api/v1/hypotheses/generate/{job_id}", headers=auth_headers
            )
            body = status_resp.json()
            if body["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

    assert body["status"] == "completed"
    hypothesis_id = body["hypothesis_id"]

    get_resp = await client.get(f"/api/v1/hypotheses/{hypothesis_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    hyp = get_resp.json()
    assert hyp["created_by"] == "llm"
    assert hyp["proposed_change"] == draft.proposed_change


@pytest.mark.asyncio
async def test_generate_hypothesis_job_fails_for_missing_run(api_client, auth_headers) -> None:
    client, _ = api_client
    start_resp = await client.post(
        "/api/v1/hypotheses/generate",
        headers=auth_headers,
        json={"run_id": "run_does_not_exist"},
    )
    job_id = start_resp.json()["job_id"]

    for _ in range(50):
        status_resp = await client.get(
            f"/api/v1/hypotheses/generate/{job_id}", headers=auth_headers
        )
        body = status_resp.json()
        if body["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.02)

    assert body["status"] == "failed"
    assert "not found" in body["error"]


@pytest.mark.asyncio
async def test_generate_hypothesis_job_not_found(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/hypotheses/generate/hgen_missing0000", headers=auth_headers)
    assert resp.status_code == 404
