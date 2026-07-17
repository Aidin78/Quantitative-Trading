from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from src.core.contracts.event import EventFamily
from src.core.settings import get_settings, load_app_yaml_config, resolve_config_dir
from src.data.csv_provider import CsvDataProvider
from src.data.market_cache import get_or_download_csv
from src.db.repositories.backtest import persist_validation_result
from src.db.session import get_session_factory
from src.engine.config import EngineConfig, load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.handlers.database_handler import DatabaseEventHandler
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.handlers.websocket_handler import WebSocketEventHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import ValidationExecutionConfig, load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.config import FeaturesConfig
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
from src.validation.harness import (
    ValidationConfig,
    ValidationHarness,
    ValidationProgressCallback,
    ValidationProgressEvent,
    ValidationResult,
)
from src.validation.trial_config import build_providers_from_overrides


async def _emit_progress(
    on_progress: ValidationProgressCallback | None,
    event: ValidationProgressEvent,
) -> None:
    if on_progress is None:
        return
    maybe = on_progress(event)
    if maybe is not None:
        await maybe


def _resolve_csv(path: str | None) -> Path:
    if path:
        return Path(path)
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [
        backend_root / "tests" / "fixtures" / "sample_btc_1h.csv",
        backend_root / "tests" / "fixtures" / "ohlcv_btc_1h.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No CSV fixture found")


async def _resolve_data_csv(
    *,
    source: Literal["exchange", "csv"],
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    csv_path: str | None,
) -> Path:
    if source == "csv":
        return _resolve_csv(csv_path)
    settings = get_settings()
    return await get_or_download_csv(
        exchange_id=settings.exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )


async def run_validation_job(
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    csv_path: str | None = None,
    source: Literal["exchange", "csv"] = "exchange",
    initial_capital: float = 10000.0,
    persist_db: bool = True,
    experiment_id: str | None = None,
    revision_id: str | None = None,
    engine_config: EngineConfig | None = None,
    provider_overrides: dict[str, dict] | None = None,
    execution_config: ValidationExecutionConfig | None = None,
    features_config: tuple[FeaturesConfig, str] | None = None,
    on_progress: ValidationProgressCallback | None = None,
) -> ValidationResult:
    app = load_app_yaml_config()
    sym = symbol or app.default_symbols[0]
    tf = timeframe or app.timeframes[0]
    start_str = start_date or app.validation.default_start
    start_dt = datetime.fromisoformat(start_str).replace(tzinfo=UTC)
    if end_date:
        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=UTC)
    elif source == "exchange":
        end_dt = datetime.now(UTC)
    else:
        end_dt = None

    await _emit_progress(
        on_progress,
        ValidationProgressEvent(
            phase="data",
            message=(
                "Loading OHLCV from Binance cache…"
                if source == "exchange"
                else "Loading sample CSV…"
            ),
        ),
    )
    csv = await _resolve_data_csv(
        source=source,
        symbol=sym,
        timeframe=tf,
        start=start_dt,
        end=end_dt or datetime.now(UTC),
        csv_path=csv_path,
    )
    provider = CsvDataProvider(csv, symbol=sym, timeframe=tf)
    if end_dt is None:
        end_dt = provider._df["timestamp"].iloc[-1].to_pydatetime()
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
    await _emit_progress(
        on_progress,
        ValidationProgressEvent(
            phase="data",
            message=(
                f"Loaded {len(timestamps)} bars "
                f"({start.date().isoformat()} → {end.date().isoformat()})."
            ),
            current=len(timestamps),
            total=len(timestamps),
        ),
    )
    clock = SimulatedClock(event_time=start)
    feature_store = InMemoryFeatureStore()
    state_store = InMemoryStateStore(
        portfolio_id="portfolio_default",
        initial_cash=initial_capital,
    )
    fill_model = load_default_fill_model(resolve_config_dir())
    execution_engine = SimulatedExecutionEngine(
        fill_model,
        clock,
        config=execution_config,
        emit_events=persist_db,
    )
    log_handler = EventLogHandler(
        families=None if persist_db else {EventFamily.EXECUTION},
    )
    handlers: list = [log_handler]
    if persist_db:
        handlers.append(WebSocketEventHandler())
        handlers.append(DatabaseEventHandler(get_session_factory()))
    bus = InMemoryEventBus(handlers=handlers)
    signal_providers = (
        build_providers_from_overrides(provider_overrides)
        if provider_overrides is not None
        else load_providers(resolve_config_dir())
    )
    if features_config is not None:
        feature_config, feature_hash = features_config
        feature_builder = DefaultFeatureBuilder(
            config=feature_config,
            config_hash=feature_hash,
            store=feature_store,
        )
    else:
        feature_builder = DefaultFeatureBuilder(store=feature_store)
    runtime = PlatformRuntime(
        data_provider=provider,
        feature_builder=feature_builder,
        feature_store=feature_store,
        state_store=state_store,
        providers=signal_providers,
        decision_engine=DecisionEngine(engine_config or load_engine_config()),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
        execution_engine=execution_engine,
        persist_features=persist_db,
        emit_events=persist_db,
    )
    config = ValidationConfig(
        symbol=sym,
        timeframe=tf,
        start=start,
        end=end,
        csv_path=str(csv),
        initial_capital=initial_capital,
    )

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
    result = await harness.run(on_progress=on_progress, retain_cycles=persist_db)
    result.experiment_run_id = experiment_run_id

    if persist_db:
        await _emit_progress(
            on_progress,
            ValidationProgressEvent(
                phase="persist",
                message="Saving validation results to database…",
            ),
        )
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
