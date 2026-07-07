from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.data.csv_provider import CsvDataProvider
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.replay.engine import ReplayEngine
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore


@pytest.fixture
def runtime_with_execution(
    csv_path: Path, real_providers
) -> tuple[PlatformRuntime, EventLogHandler]:
    event_time = datetime(2026, 1, 5, 3, 0, 0, tzinfo=UTC)
    clock = SimulatedClock(
        event_time=event_time,
        processing_time=event_time + timedelta(seconds=2),
    )
    feature_store = InMemoryFeatureStore()
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler])
    fill_model = load_default_fill_model()
    execution_engine = SimulatedExecutionEngine(fill_model, clock)
    runtime = PlatformRuntime(
        data_provider=CsvDataProvider(csv_path),
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=InMemoryStateStore(portfolio_id="portfolio_default"),
        providers=real_providers,
        decision_engine=DecisionEngine(load_engine_config()),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
        execution_engine=execution_engine,
    )
    return runtime, log_handler


@pytest.mark.asyncio
async def test_runtime_emits_execution_events_when_approved(
    runtime_with_execution: tuple[PlatformRuntime, EventLogHandler],
) -> None:
    runtime, log_handler = runtime_with_execution
    result = await runtime.run_cycle("BTC/USDT", "1h", correlation_id="exec_test")
    if result.decision.is_approved:
        assert len(result.execution_events) > 0
        assert any(e.event_family == EventFamily.EXECUTION for e in result.execution_events)


@pytest.mark.asyncio
async def test_strict_replay_rebuilds_cycle(
    runtime_with_execution: tuple[PlatformRuntime, EventLogHandler],
) -> None:
    runtime, log_handler = runtime_with_execution
    correlation_id = "replay_cycle_1"
    await runtime.run_cycle("BTC/USDT", "1h", correlation_id=correlation_id)
    engine = ReplayEngine(log_handler.events)
    replay = engine.replay_cycle(correlation_id)
    assert replay.correlation_id == correlation_id
    assert len(replay.timeline) > 0
    assert EventFamily.MARKET in replay.families_present
    assert EventFamily.DECISION in replay.families_present
