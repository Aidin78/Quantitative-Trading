from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.settings import get_settings
from src.db.base import Base
from src.db.session import get_async_engine
from src.governance.candidate_store import run_candidate_evaluation
from src.main import app
from src.validation.optimization_scoring import OptimizationResult


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
async def test_create_and_get_candidate(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={"experiment_id": "exp_1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "candidate"
    candidate_id = body["candidate_id"]

    get_resp = await client.get(f"/api/v1/candidates/{candidate_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["experiment_id"] == "exp_1"


@pytest.mark.asyncio
async def test_get_candidate_not_found(api_client, auth_headers) -> None:
    client, _ = api_client
    resp = await client.get("/api/v1/candidates/cand_missing0000", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_without_evaluation_returns_400(api_client, auth_headers) -> None:
    client, _ = api_client
    create_resp = await client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={"experiment_id": "exp_1"},
    )
    candidate_id = create_resp.json()["candidate_id"]

    resp = await client.post(
        f"/api/v1/candidates/{candidate_id}/promote",
        headers=auth_headers,
        json={"to_state": "challenger"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_promote_after_accepted_evaluation(api_client, auth_headers) -> None:
    client, factory = api_client
    create_resp = await client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={"experiment_id": "exp_1"},
    )
    candidate_id = create_resp.json()["candidate_id"]

    from datetime import UTC, datetime

    from src.validation.optimization_scoring import TrialResult

    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = OptimizationResult(
        sweep_id="sweep_test",
        symbol="BTC/USDT",
        timeframe="1h",
        train_start=now,
        train_end=now,
        test_start=now,
        test_end=now,
        holdout_valid=True,
        holdout_outcome={
            "total_trades": 40,
            "regime_analysis": {
                "by_regime": {"UP_HIGH": {"trades": 20}, "DOWN_LOW": {"trades": 20}}
            },
        },
        best=TrialResult(
            trial_id="trial_1",
            params={},
            train_score=1.0,
            train_outcome={},
            fold_scores=[1.0, 1.1, 0.9],
            fold_std=0.5,
        ),
    )
    async with factory() as session:
        await run_candidate_evaluation(session, candidate_id, result)
        await session.commit()

    eval_resp = await client.get(
        f"/api/v1/candidates/{candidate_id}/evaluations", headers=auth_headers
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["items"][0]["decision"] == "accepted"

    promote_resp = await client.post(
        f"/api/v1/candidates/{candidate_id}/promote",
        headers=auth_headers,
        json={"to_state": "challenger"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["state"] == "challenger"
