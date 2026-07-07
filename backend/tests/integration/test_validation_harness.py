from __future__ import annotations

from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.data.csv_provider import CsvDataProvider
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import ExecutionEventType
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore
from src.validation.harness import ValidationConfig, ValidationHarness


@pytest.fixture
def validation_stack(csv_path: Path, real_providers):
    df = CsvDataProvider(csv_path)._df
    start = df["timestamp"].iloc[0].to_pydatetime()
    end = df["timestamp"].iloc[-1].to_pydatetime()
    clock = SimulatedClock(event_time=start)
    provider = CsvDataProvider(csv_path)
    feature_store = InMemoryFeatureStore()
    state_store = InMemoryStateStore(portfolio_id="portfolio_default")
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler])
    fill_model = load_default_fill_model()
    execution_engine = SimulatedExecutionEngine(fill_model, clock)
    runtime = PlatformRuntime(
        data_provider=provider,
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=state_store,
        providers=real_providers,
        decision_engine=DecisionEngine(load_engine_config()),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
        execution_engine=execution_engine,
    )
    config = ValidationConfig(
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    harness = ValidationHarness(runtime, provider, clock, log_handler, config=config)
    return harness, log_handler


@pytest.mark.asyncio
async def test_validation_harness_runs_bar_loop(validation_stack) -> None:
    harness, log_handler = validation_stack
    result = await harness.run()
    assert len(result.cycles) > 0
    assert result.engine_metrics["total_cycles"] == len(result.cycles)
    assert log_handler.events


@pytest.mark.asyncio
async def test_validation_event_chain_includes_execution_when_approved(validation_stack) -> None:
    harness, _ = validation_stack
    result = await harness.run()
    families = {e.event_family for e in result.events}
    assert EventFamily.MARKET in families
    assert EventFamily.DECISION in families
    approved_cycles = [c for c in result.cycles if c.decision.is_approved]
    if approved_cycles:
        assert EventFamily.EXECUTION in families
        assert any(e.event_type == ExecutionEventType.ORDER_INTENT_CREATED for e in result.events)


@pytest.mark.asyncio
async def test_validation_outcome_metrics_include_capital_fields(validation_stack) -> None:
    harness, _ = validation_stack
    result = await harness.run()
    outcome = result.outcome_metrics
    assert "initial_capital" in outcome
    assert "ending_equity" in outcome
    assert "return_pct" in outcome
    assert outcome["positions_closed"] == outcome["total_trades"]
    if outcome["positions_opened"] > 0:
        assert outcome["total_trades"] > 0
        assert 0.0 <= outcome["win_rate"] <= 1.0
