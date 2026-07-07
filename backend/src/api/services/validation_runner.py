from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.core.settings import load_app_yaml_config, resolve_config_dir
from src.data.csv_provider import CsvDataProvider
from src.db.repositories.backtest import persist_validation_result
from src.db.session import get_session_factory
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.handlers.database_handler import DatabaseEventHandler
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.handlers.websocket_handler import WebSocketEventHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.governance.revision_store import (
    compute_config_revision,
    ensure_current_revision,
    save_revision,
)
from src.providers import load_providers
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore
from src.validation.harness import ValidationConfig, ValidationHarness, ValidationResult


def _resolve_csv(path: str | None) -> Path:
    if path:
        return Path(path)
    candidates = [
        Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample_btc_1h.csv",
        Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ohlcv_btc_1h.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No CSV fixture found")


async def run_validation_job(
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    csv_path: str | None = None,
    persist_db: bool = True,
    experiment_id: str | None = None,
    revision_id: str | None = None,
) -> ValidationResult:
    app = load_app_yaml_config()
    sym = symbol or app.default_symbols[0]
    tf = timeframe or app.timeframes[0]
    start_str = start_date or app.validation.default_start
    csv = _resolve_csv(csv_path)
    provider = CsvDataProvider(csv, symbol=sym, timeframe=tf)
    end_dt = (
        datetime.fromisoformat(end_date).replace(tzinfo=UTC)
        if end_date
        else provider._df["timestamp"].iloc[-1].to_pydatetime()
    )
    timestamps = provider.timestamps(
        sym,
        tf,
        datetime.fromisoformat(start_str).replace(tzinfo=UTC),
        end_dt,
    )
    if not timestamps:
        raise ValueError("No bars in range")

    start = timestamps[0]
    end = timestamps[-1]
    clock = SimulatedClock(event_time=start)
    feature_store = InMemoryFeatureStore()
    state_store = InMemoryStateStore(portfolio_id="portfolio_default")
    fill_model = load_default_fill_model(resolve_config_dir())
    execution_engine = SimulatedExecutionEngine(fill_model, clock)
    log_handler = EventLogHandler()
    handlers: list = [log_handler, WebSocketEventHandler()]
    if persist_db:
        handlers.append(DatabaseEventHandler(get_session_factory()))
    bus = InMemoryEventBus(handlers=handlers)
    runtime = PlatformRuntime(
        data_provider=provider,
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=state_store,
        providers=load_providers(resolve_config_dir()),
        decision_engine=DecisionEngine(load_engine_config()),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
        execution_engine=execution_engine,
    )
    config = ValidationConfig(symbol=sym, timeframe=tf, start=start, end=end, csv_path=str(csv))

    rev_id = revision_id
    exp_id = experiment_id
    experiment_run_id: str | None = None
    if persist_db:
        async with get_session_factory()() as session:
            if not rev_id:
                revision = await ensure_current_revision(session, label="validation")
                rev_id = revision.revision_id
            else:
                from src.governance.revision_store import get_revision

                revision = await get_revision(session, rev_id)
                if revision is None:
                    revision = compute_config_revision(label="validation")
                    await save_revision(session, revision)
                    rev_id = revision.revision_id
            if not exp_id:
                from src.governance.experiment_store import create_experiment

                experiment = await create_experiment(
                    session,
                    revision_id=rev_id,
                    name=f"validation_{sym}_{tf}",
                    mode="validation",
                    symbols=(sym,),
                    timeframes=(tf,),
                )
                exp_id = experiment.experiment_id
            from src.governance.experiment_store import create_experiment_run

            run = await create_experiment_run(
                session,
                experiment_id=exp_id,
                revision_id=rev_id,
            )
            experiment_run_id = run.run_id
            await session.commit()

    harness = ValidationHarness(
        runtime,
        provider,
        clock,
        log_handler,
        config=config,
        revision_id=rev_id,
        experiment_id=exp_id,
    )
    result = await harness.run()
    result.experiment_run_id = experiment_run_id

    if persist_db:
        async with get_session_factory()() as session:
            await persist_validation_result(
                session,
                result,
                revision_id=rev_id,
                experiment_id=exp_id,
            )
            if experiment_run_id:
                from src.governance.experiment_store import complete_experiment_run

                outcome = result.outcome_metrics or {}
                await complete_experiment_run(
                    session,
                    experiment_run_id,
                    status="completed",
                    metrics_summary={
                        "total_trades": float(outcome.get("total_trades", 0)),
                        "win_rate": float(outcome.get("win_rate", 0)),
                        "total_pnl": float(outcome.get("total_pnl", 0)),
                    },
                )
            await session.commit()

    return result


def new_validation_job_id() -> str:
    return f"val_{uuid.uuid4().hex[:12]}"
