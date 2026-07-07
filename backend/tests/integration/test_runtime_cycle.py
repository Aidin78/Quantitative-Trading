from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.data.csv_provider import CsvDataProvider
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import DecisionEventType
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.handlers.logging_handler import LoggingEventHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore


@pytest.fixture
def runtime(csv_path: Path, real_providers) -> PlatformRuntime:
    event_time = datetime(2026, 1, 5, 3, 0, 0, tzinfo=UTC)
    clock = SimulatedClock(
        event_time=event_time,
        processing_time=event_time + timedelta(seconds=2),
    )
    feature_store = InMemoryFeatureStore()
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler, LoggingEventHandler()])
    return PlatformRuntime(
        data_provider=CsvDataProvider(csv_path),
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=InMemoryStateStore(portfolio_id="portfolio_default"),
        providers=real_providers,
        decision_engine=DecisionEngine(),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
    )


@pytest.mark.asyncio
async def test_full_runtime_cycle(runtime: PlatformRuntime) -> None:
    result = await runtime.run_cycle("BTC/USDT", "1h", correlation_id="integration_cycle")
    assert result.correlation_id == "integration_cycle"
    assert result.feature_set.feature_set_id
    assert result.snapshot.snapshot_id
    assert len(result.signals) == 2
    assert len(result.events) >= 5


@pytest.mark.asyncio
async def test_decision_events_include_state_snapshot_id(runtime: PlatformRuntime) -> None:
    result = await runtime.run_cycle("BTC/USDT", "1h")
    decision_events = [e for e in result.events if e.event_family == EventFamily.DECISION]
    assert len(decision_events) >= 2
    made = next(e for e in decision_events if e.event_type == DecisionEventType.DECISION_MADE)
    assert made.payload["state_snapshot_id"] == result.snapshot.snapshot_id
    outcome_type = (
        DecisionEventType.DECISION_APPROVED
        if result.decision.is_approved
        else DecisionEventType.DECISION_REJECTED
    )
    outcome = next(e for e in decision_events if e.event_type == outcome_type)
    assert outcome.payload["state_snapshot_id"] == result.snapshot.snapshot_id


@pytest.mark.asyncio
async def test_event_time_differs_from_processing_time(runtime: PlatformRuntime) -> None:
    result = await runtime.run_cycle("BTC/USDT", "1h")
    decision_events = [e for e in result.events if e.event_family == EventFamily.DECISION]
    for event in decision_events:
        assert event.event_time != event.processing_time


@pytest.mark.asyncio
async def test_event_chain_has_market_signal_decision(runtime: PlatformRuntime) -> None:
    result = await runtime.run_cycle("BTC/USDT", "1h", correlation_id="chain_test")
    families = {e.event_family for e in result.events}
    assert EventFamily.MARKET in families
    assert EventFamily.SIGNAL in families
    assert EventFamily.DECISION in families
    assert all(e.correlation_id == "chain_test" for e in result.events)


@pytest.mark.asyncio
async def test_feature_set_persisted_in_store(runtime: PlatformRuntime) -> None:
    result = await runtime.run_cycle("BTC/USDT", "1h")
    record = runtime._feature_store.get(result.feature_set.feature_set_id)
    assert record.feature_version == result.feature_set.feature_version
    assert record.market_context == result.context


@pytest.mark.asyncio
async def test_feature_build_before_providers(
    monkeypatch: pytest.MonkeyPatch, runtime: PlatformRuntime
) -> None:
    order: list[str] = []
    original_build = runtime._feature_builder.build
    original_analyze = runtime._providers[0].analyze

    def tracked_build(*args, **kwargs):  # noqa: ANN002, ANN003
        order.append("build")
        return original_build(*args, **kwargs)

    def tracked_analyze(*args, **kwargs):  # noqa: ANN002, ANN003
        order.append("analyze")
        return original_analyze(*args, **kwargs)

    monkeypatch.setattr(runtime._feature_builder, "build", tracked_build)
    monkeypatch.setattr(runtime._providers[0], "analyze", tracked_analyze)
    await runtime.run_cycle("BTC/USDT", "1h")
    assert order.index("build") < order.index("analyze")


def test_runtime_has_no_forbidden_imports() -> None:
    runtime_root = Path(__file__).resolve().parents[2] / "src" / "runtime"
    forbidden = ("telegram", "websocket", "sqlalchemy", "asyncpg", "handlers.database")
    for path in runtime_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in content, f"{path} contains forbidden: {token}"
