from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.data.csv_provider import CsvDataProvider
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import DecisionEventType, SignalEventType
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.providers.base import ProviderConfig
from src.providers.registry import instantiate_provider
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore
from src.validation.harness import ValidationConfig, ValidationHarness


def _build_runtime(
    csv_path: Path,
    providers,
    *,
    event_time: datetime | None = None,
    with_execution: bool = False,
) -> tuple[PlatformRuntime, EventLogHandler, SimulatedClock]:
    if event_time is None:
        event_time = datetime(2026, 1, 5, 3, 0, 0, tzinfo=UTC)
    clock = SimulatedClock(
        event_time=event_time,
        processing_time=event_time + timedelta(seconds=2),
    )
    feature_store = InMemoryFeatureStore()
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler])
    execution_engine = None
    if with_execution:
        fill_model = load_default_fill_model()
        execution_engine = SimulatedExecutionEngine(fill_model, clock)
    runtime = PlatformRuntime(
        data_provider=CsvDataProvider(csv_path),
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=InMemoryStateStore(portfolio_id="portfolio_default"),
        providers=providers,
        decision_engine=DecisionEngine(load_engine_config()),
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_default",
        mode="validation",
        execution_engine=execution_engine,
    )
    return runtime, log_handler, clock


@pytest.mark.asyncio
async def test_market_structure_analyze_without_error(csv_path: Path, real_providers) -> None:
    ms = instantiate_provider(ProviderConfig(provider_id="market_structure", enabled=True))
    runtime, _, _ = _build_runtime(csv_path, [ms])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "market_structure"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_volume_order_flow_analyze_without_error(csv_path: Path, real_providers) -> None:
    vol = instantiate_provider(ProviderConfig(provider_id="volume_order_flow", enabled=True))
    runtime, _, _ = _build_runtime(csv_path, [vol])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "volume_order_flow"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_supertrend_trend_analyze_without_error(csv_path: Path, real_providers) -> None:
    st = instantiate_provider(ProviderConfig(provider_id="supertrend_trend", enabled=True))
    runtime, _, _ = _build_runtime(csv_path, [st])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "supertrend_trend"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_bollinger_reversion_analyze_without_error(csv_path: Path, real_providers) -> None:
    bb = instantiate_provider(ProviderConfig(provider_id="bollinger_reversion", enabled=True))
    runtime, _, _ = _build_runtime(csv_path, [bb])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "bollinger_reversion"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_adx_trend_strength_analyze_without_error(csv_path: Path, real_providers) -> None:
    adx = instantiate_provider(ProviderConfig(provider_id="adx_trend_strength", enabled=True))
    runtime, _, _ = _build_runtime(csv_path, [adx])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "adx_trend_strength"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_macd_momentum_analyze_without_error(csv_path: Path, real_providers) -> None:
    macd = next(p for p in real_providers if p.provider_id == "macd_momentum")
    runtime, _, _ = _build_runtime(csv_path, [macd])
    result = await runtime.run_cycle("BTC/USDT", "1h")
    assert len(result.signals) == 1
    assert result.signals[0].provider_id == "macd_momentum"
    assert result.signals[0].side in {"BUY", "SELL", "HOLD"}


@pytest.mark.asyncio
async def test_real_providers_full_cycle(csv_path: Path, real_providers) -> None:
    runtime, _, _ = _build_runtime(csv_path, real_providers)
    result = await runtime.run_cycle("BTC/USDT", "1h", correlation_id="real_providers_cycle")
    assert len(result.signals) == 3
    assert {s.provider_id for s in result.signals} == {
        "ema_crossover",
        "rsi_divergence",
        "macd_momentum",
    }
    decision_events = [e for e in result.events if e.event_family == EventFamily.DECISION]
    assert any(e.event_type == DecisionEventType.DECISION_MADE for e in decision_events)
    made = next(e for e in decision_events if e.event_type == DecisionEventType.DECISION_MADE)
    assert made.payload["state_snapshot_id"] == result.snapshot.snapshot_id


@pytest.mark.asyncio
async def test_disabled_provider_emits_skipped_event(csv_path: Path, real_providers) -> None:
    providers = [
        instantiate_provider(ProviderConfig(provider_id="ema_crossover", enabled=False)),
        next(p for p in real_providers if p.provider_id == "rsi_divergence"),
    ]
    runtime, _, _ = _build_runtime(csv_path, providers)
    result = await runtime.run_cycle("BTC/USDT", "1h")
    skipped = [e for e in result.events if e.event_type == SignalEventType.PROVIDER_SKIPPED]
    assert len(skipped) == 1
    assert skipped[0].payload["provider_id"] == "ema_crossover"
    assert len(result.signals) == 1


@pytest.mark.asyncio
async def test_validation_harness_with_real_providers_reproducible(
    csv_path: Path, real_providers
) -> None:
    df = CsvDataProvider(csv_path)._df
    start = df["timestamp"].iloc[0].to_pydatetime()
    end = df["timestamp"].iloc[-1].to_pydatetime()
    clock = SimulatedClock(event_time=start)
    provider = CsvDataProvider(csv_path)
    feature_store = InMemoryFeatureStore()
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler])
    fill_model = load_default_fill_model()
    execution_engine = SimulatedExecutionEngine(fill_model, clock)
    runtime = PlatformRuntime(
        data_provider=provider,
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
    config = ValidationConfig(symbol="BTC/USDT", timeframe="1h", start=start, end=end)
    harness = ValidationHarness(runtime, provider, clock, log_handler, config=config)
    first = await harness.run()
    second = await harness.run()
    assert first.engine_metrics["total_cycles"] == second.engine_metrics["total_cycles"]
    assert first.engine_metrics["approval_rate"] == second.engine_metrics["approval_rate"]
