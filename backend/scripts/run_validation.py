#!/usr/bin/env python3
"""CLI entry point for validation harness."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running as script from repo
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.core.settings import load_app_yaml_config, resolve_config_dir
from src.data.csv_provider import CsvDataProvider
from src.db.repositories.backtest import persist_validation_result
from src.db.session import get_async_engine, get_session_factory, init_db
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.handlers.database_handler import DatabaseEventHandler
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.providers import load_providers
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore
from src.validation.harness import ValidationConfig, ValidationHarness
from src.validation.report import format_report, write_report


def _parse_args() -> argparse.Namespace:
    app = load_app_yaml_config()
    parser = argparse.ArgumentParser(description="Run validation harness on historical CSV data")
    parser.add_argument("--symbol", default=app.default_symbols[0])
    parser.add_argument("--timeframe", default=app.timeframes[0])
    parser.add_argument("--start", default=app.validation.default_start)
    parser.add_argument("--end", default=None)
    parser.add_argument("--csv-path", default=None)
    parser.add_argument("--output", default=None, help="JSON report output path")
    parser.add_argument("--no-db", action="store_true", help="Skip database persistence")
    return parser.parse_args()


def _resolve_csv(path: str | None) -> Path:
    if path:
        return Path(path)
    candidates = [
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_btc_1h.csv",
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ohlcv_btc_1h.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No CSV fixture found; pass --csv-path")


async def _run() -> int:
    args = _parse_args()
    csv_path = _resolve_csv(args.csv_path)
    provider = CsvDataProvider(csv_path, symbol=args.symbol, timeframe=args.timeframe)
    timestamps = provider.timestamps(
        args.symbol,
        args.timeframe,
        datetime.fromisoformat(args.start).replace(tzinfo=UTC),
        datetime.fromisoformat(args.end).replace(tzinfo=UTC)
        if args.end
        else provider._df["timestamp"].iloc[-1].to_pydatetime(),
    )
    if not timestamps:
        print("No bars in range", file=sys.stderr)
        return 1

    start = timestamps[0]
    end = timestamps[-1]
    clock = SimulatedClock(event_time=start)
    feature_store = InMemoryFeatureStore()
    state_store = InMemoryStateStore(portfolio_id="portfolio_default")
    fill_model = load_default_fill_model(resolve_config_dir())
    execution_engine = SimulatedExecutionEngine(fill_model, clock)

    log_handler = EventLogHandler()
    handlers = [log_handler]
    if not args.no_db:
        engine = get_async_engine()
        await init_db(engine)
        db_handler = DatabaseEventHandler(get_session_factory(engine))
        handlers.append(db_handler)

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

    config = ValidationConfig(symbol=args.symbol, timeframe=args.timeframe, start=start, end=end)
    harness = ValidationHarness(runtime, provider, clock, log_handler, config=config)
    result = await harness.run()

    report_text = format_report(result)
    print(report_text)

    if args.output:
        write_report(result, Path(args.output))

    if not args.no_db:
        async with get_session_factory()() as session:
            await persist_validation_result(session, result)

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
