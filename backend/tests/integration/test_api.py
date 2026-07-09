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
    body = resp.json()
    assert body["phase"] == "8-production-mvp"
    assert body["default_symbol"] == "BTC/USDT"
    assert body["default_timeframe"] == "1h"


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
        mode="paper",
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
        mode="paper",
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
async def test_validation_decisions_excluded_from_dashboard(api_client, auth_headers) -> None:
    client, factory = api_client
    from datetime import UTC, datetime

    from src.core.contracts.event import EventFamily
    from src.db.repositories.backtest import persist_event
    from src.db.repositories.decision import persist_decision_from_event

    def _make(decision_id: str, mode: str):
        return build_envelope(
            event_family=EventFamily.DECISION,
            event_type=DecisionEventType.DECISION_MADE,
            event_time=datetime.now(UTC),
            processing_time=datetime.now(UTC),
            correlation_id=f"corr_{decision_id}",
            symbol="BTC/USDT",
            timeframe="1h",
            mode=mode,
            payload={
                "decision_id": decision_id,
                "result": "approved",
                "state_snapshot_id": "snap_x",
                "decision_log": {
                    "market_filter": {"passed": True},
                    "provider_signals": [],
                    "aggregation": {"method": "majority", "side": "BUY", "confidence": 0.7},
                    "risk_check": {"passed": True, "checks": [], "state_snapshot_id": "snap_x"},
                    "state_snapshot_id": "snap_x",
                    "portfolio_version": 1,
                    "risk_state_version": 1,
                },
            },
        )

    val_event = _make("dec_val_only", "validation")
    paper_event = _make("dec_paper_only", "paper")
    async with factory() as session:
        await persist_decision_from_event(session, val_event)
        await persist_decision_from_event(session, paper_event)
        await persist_event(session, val_event)
        await persist_event(session, paper_event)
        await session.commit()

    default_resp = await client.get("/api/v1/decisions", headers=auth_headers)
    default_ids = {item["id"] for item in default_resp.json()["items"]}
    assert "dec_paper_only" in default_ids
    assert "dec_val_only" not in default_ids

    all_resp = await client.get("/api/v1/decisions?scope=all", headers=auth_headers)
    all_ids = {item["id"] for item in all_resp.json()["items"]}
    assert "dec_val_only" in all_ids
    assert "dec_paper_only" in all_ids

    stats = await client.get("/api/v1/engine/stats", headers=auth_headers)
    assert stats.json()["decisions_today"] == 1
    stats_all = await client.get("/api/v1/engine/stats?scope=all", headers=auth_headers)
    assert stats_all.json()["decisions_today"] == 2


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
    items = resp.json()["items"]
    assert len(items) >= 2
    ema = next(item for item in items if item["provider_id"] == "ema_crossover")
    assert ema["rules"]
    assert ema["param_fields"]
    assert ema["default_config"]
    macd = next(item for item in items if item["provider_id"] == "macd_momentum")
    assert "rsi_14" not in macd["required_features"]
    assert "macd_histogram" in macd["required_features"]


@pytest.mark.asyncio
async def test_provider_reset(api_client) -> None:
    client, _ = api_client
    patch_resp = await client.patch(
        "/api/v1/providers/ema_crossover",
        json={"params": {"min_confidence": 0.99}},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["params"]["min_confidence"] == 0.99

    reset_resp = await client.post("/api/v1/providers/ema_crossover/reset")
    assert reset_resp.status_code == 200
    body = reset_resp.json()
    assert body["params"]["min_confidence"] == 0.6
    assert body["rules"]


@pytest.mark.asyncio
async def test_provider_baseline_enables_all_core_providers(api_client) -> None:
    client, _ = api_client
    await client.patch(
        "/api/v1/providers/ema_crossover",
        json={"enabled": False},
    )
    await client.patch(
        "/api/v1/providers/rsi_divergence",
        json={"enabled": False},
    )

    resp = await client.post("/api/v1/providers/baseline")
    assert resp.status_code == 200
    items = {item["provider_id"]: item for item in resp.json()["items"]}
    for provider_id in ("ema_crossover", "rsi_divergence", "macd_momentum"):
        assert provider_id in items
        assert items[provider_id]["enabled"] is True


@pytest.mark.asyncio
async def test_validation_runs_and_compare(api_client, auth_headers) -> None:
    from datetime import UTC, datetime

    from src.db.models import BacktestRunRow

    client, factory = api_client
    async with factory() as session:
        session.add(
            BacktestRunRow(
                run_id="run_test_a",
                symbol="BTC/USDT",
                timeframe="1h",
                config={
                    "start": "2026-06-01T00:00:00+00:00",
                    "end": "2026-06-30T00:00:00+00:00",
                    "initial_capital": 10000.0,
                    "revision_id": "rev_a",
                },
                metrics={
                    "engine": {"approved": 10},
                    "outcome": {
                        "total_trades": 5,
                        "win_rate": 0.6,
                        "return_pct": 2.5,
                        "score": 12.0,
                        "sharpe_ratio": 0.8,
                        "profit_factor": 1.4,
                        "max_drawdown_pct": 3.0,
                        "total_pnl": 250.0,
                    },
                },
                started_at=datetime(2026, 6, 1, tzinfo=UTC),
                completed_at=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )
        session.add(
            BacktestRunRow(
                run_id="run_test_b",
                symbol="BTC/USDT",
                timeframe="1h",
                config={
                    "start": "2026-07-01T00:00:00+00:00",
                    "end": "2026-07-31T00:00:00+00:00",
                    "initial_capital": 10000.0,
                    "revision_id": "rev_b",
                },
                metrics={
                    "engine": {"approved": 8},
                    "outcome": {
                        "total_trades": 4,
                        "win_rate": 0.5,
                        "return_pct": 1.0,
                        "score": 5.0,
                        "sharpe_ratio": 0.4,
                        "profit_factor": 1.1,
                        "max_drawdown_pct": 5.0,
                        "total_pnl": 100.0,
                    },
                },
                started_at=datetime(2026, 7, 1, tzinfo=UTC),
                completed_at=datetime(2026, 7, 31, tzinfo=UTC),
            )
        )
        await session.commit()

    runs_resp = await client.get("/api/v1/validation/runs", headers=auth_headers)
    assert runs_resp.status_code == 200
    items = runs_resp.json()["items"]
    assert any(item["run_id"] == "run_test_a" for item in items)
    assert any(item["run_id"] == "run_test_b" for item in items)

    compare_resp = await client.get(
        "/api/v1/validation/compare?a=run_test_a&b=run_test_b",
        headers=auth_headers,
    )
    assert compare_resp.status_code == 200
    body = compare_resp.json()
    assert body["overall_winner"] == "a"
    assert body["metrics"]["return_pct"]["winner"] == "a"
    assert body["metrics"]["max_drawdown_pct"]["winner"] == "a"


@pytest.mark.asyncio
async def test_validation_runs_delete_and_bulk_delete(api_client, auth_headers) -> None:
    from datetime import UTC, datetime

    from src.db.models import BacktestRunRow, SimulatedTradeRow

    client, factory = api_client
    async with factory() as session:
        session.add(
            BacktestRunRow(
                run_id="run_delete_a",
                symbol="BTC/USDT",
                timeframe="1h",
                config={"start": "2026-06-01", "end": "2026-06-30"},
                metrics={"engine": {}, "outcome": {"total_trades": 1, "score": 1.0}},
                started_at=datetime(2026, 6, 1, tzinfo=UTC),
                completed_at=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )
        session.add(
            BacktestRunRow(
                run_id="run_delete_b",
                symbol="BTC/USDT",
                timeframe="1h",
                config={"start": "2026-07-01", "end": "2026-07-31"},
                metrics={"engine": {}, "outcome": {"total_trades": 2, "score": 2.0}},
                started_at=datetime(2026, 7, 1, tzinfo=UTC),
                completed_at=datetime(2026, 7, 31, tzinfo=UTC),
            )
        )
        session.add(
            SimulatedTradeRow(
                trade_id="trade_delete_a",
                run_id="run_delete_a",
                position_id="pos_a",
                correlation_id="cycle_a",
                symbol="BTC/USDT",
                pnl=10.0,
                exit_reason="take_profit",
                payload={},
            )
        )
        await session.commit()

    delete_one = await client.delete(
        "/api/v1/validation/runs/run_delete_a",
        headers=auth_headers,
    )
    assert delete_one.status_code == 200
    assert delete_one.json()["deleted"] == "run_delete_a"

    bulk = await client.post(
        "/api/v1/validation/runs/bulk-delete",
        headers=auth_headers,
        json={"run_ids": ["run_delete_b", "run_missing"]},
    )
    assert bulk.status_code == 200
    body = bulk.json()
    assert body["deleted"] == ["run_delete_b"]
    assert body["not_found"] == ["run_missing"]

    async with factory() as session:
        assert await session.get(BacktestRunRow, "run_delete_a") is None
        assert await session.get(BacktestRunRow, "run_delete_b") is None
        assert await session.get(SimulatedTradeRow, "trade_delete_a") is None


@pytest.mark.asyncio
async def test_optimization_api_apply(api_client, auth_headers, monkeypatch) -> None:
    import asyncio
    from datetime import UTC, datetime

    from src.api.services.optimization_service import optimization_sweeps
    from src.validation.optimizer import OptimizationResult, TrialResult

    async def fast_run(**kwargs):
        trial = TrialResult(
            trial_id="trial_test",
            params={
                "min_confidence": 0.65,
                "min_risk_reward": 1.5,
                "min_agreeing_providers": 1,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 3.0,
                "max_bars_in_trade": 48,
            },
            train_score=10.0,
            train_outcome={"total_trades": 1},
            test_score=12.0,
            test_outcome={
                "monthly_breakdown": [{"pnl": 1}],
                "total_trades": 30,
                "return_pct": 5.0,
            },
            stability=1.0,
        )
        return OptimizationResult(
            sweep_id="sweep_test",
            symbol="BTC/USDT",
            timeframe="1h",
            train_start=datetime(2026, 1, 1, tzinfo=UTC),
            train_end=datetime(2026, 1, 3, tzinfo=UTC),
            test_start=datetime(2026, 1, 3, tzinfo=UTC),
            test_end=datetime(2026, 1, 5, tzinfo=UTC),
            trials=[trial],
            best=trial,
            best_valid=True,
        )

    monkeypatch.setattr("src.api.v1.optimization.run_optimization", fast_run)
    monkeypatch.setattr(
        "src.api.v1.optimization.write_engine_config",
        lambda patch: {"patched": True},
    )
    monkeypatch.setattr(
        "src.api.v1.optimization.write_provider_config",
        lambda provider_id, patch: {"provider_id": provider_id},
    )
    monkeypatch.setattr(
        "src.api.v1.optimization.write_validation_settings",
        lambda patch: patch,
    )
    monkeypatch.setattr(
        "src.api.v1.optimization.write_features_config",
        lambda **kwargs: kwargs,
    )

    client, _ = api_client
    start = await client.post(
        "/api/v1/optimization/run",
        headers=auth_headers,
        json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2026-01-01",
            "end_date": "2026-01-05",
            "source": "csv",
            "max_trials": 1,
            "top_k": 1,
        },
    )
    assert start.status_code == 200
    sweep_id = start.json()["id"]

    for _ in range(50):
        sweep = optimization_sweeps.get(sweep_id)
        if sweep and sweep.status == "completed":
            break
        await asyncio.sleep(0.05)
    assert sweep is not None
    assert sweep.status == "completed"

    apply_resp = await client.post(
        f"/api/v1/optimization/{sweep_id}/apply",
        headers=auth_headers,
    )
    assert apply_resp.status_code == 200
    body = apply_resp.json()
    assert body["revision_id"].startswith("rev_")
    assert body["applied_params"]["min_confidence"] == 0.65


@pytest.mark.asyncio
async def test_experiments_delete_and_bulk_delete(api_client, auth_headers) -> None:
    client, factory = api_client

    created_ids: list[str] = []
    for name in ("exp-delete-a", "exp-delete-b"):
        resp = await client.post(
            "/api/v1/experiments",
            headers=auth_headers,
            json={"name": name, "mode": "validation"},
        )
        assert resp.status_code == 200
        created_ids.append(resp.json()["experiment_id"])

    delete_one = await client.delete(
        f"/api/v1/experiments/{created_ids[0]}",
        headers=auth_headers,
    )
    assert delete_one.status_code == 200
    assert delete_one.json()["deleted"] == created_ids[0]

    bulk = await client.post(
        "/api/v1/experiments/bulk-delete",
        headers=auth_headers,
        json={"experiment_ids": [created_ids[1], "exp_does_not_exist"]},
    )
    assert bulk.status_code == 200
    body = bulk.json()
    assert body["deleted"] == [created_ids[1]]
    assert body["not_found"] == ["exp_does_not_exist"]
    assert body["deleted_count"] == 1

    list_resp = await client.get("/api/v1/experiments", headers=auth_headers)
    assert list_resp.status_code == 200
    remaining = {item["experiment_id"] for item in list_resp.json()["items"]}
    assert created_ids[0] not in remaining
    assert created_ids[1] not in remaining

    async with factory() as session:
        from src.governance.experiment_store import get_experiment

        assert await get_experiment(session, created_ids[0]) is None
        assert await get_experiment(session, created_ids[1]) is None
