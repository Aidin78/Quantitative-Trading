from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.core.contracts.event import EventBus
from src.core.settings import get_settings, load_app_yaml_config, resolve_config_dir
from src.data.live_provider import LiveProvider
from src.db.session import get_session_factory
from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from src.events.bus_factory import create_event_bus
from src.events.handler_factory import build_handlers
from src.execution.config import load_default_fill_model
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.providers import load_providers
from src.runtime.clocks import WallClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore


@dataclass
class LiveStack:
    runtime: PlatformRuntime
    bus: EventBus
    provider: LiveProvider
    clock: WallClock


async def build_live_stack(
    mode: Literal["paper", "live"],
    *,
    persist_db: bool = True,
    prefer_redis: bool = True,
) -> LiveStack:
    settings = get_settings()
    provider = LiveProvider(
        exchange_id=settings.exchange_id,
        api_key=settings.exchange_api_key,
        api_secret=settings.exchange_api_secret,
    )
    clock = WallClock()
    feature_store = InMemoryFeatureStore()
    state_store = InMemoryStateStore(portfolio_id="portfolio_default")
    fill_model = load_default_fill_model(resolve_config_dir())
    execution_engine = SimulatedExecutionEngine(fill_model, clock, mode=mode)
    session_factory = get_session_factory() if persist_db else None
    handlers = build_handlers(mode, session_factory=session_factory, persist_db=persist_db)
    bus = await create_event_bus(handlers, prefer_redis=prefer_redis)
    runtime_mode: Literal["paper", "live"] = mode
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
        mode=runtime_mode,
        execution_engine=execution_engine,
    )
    return LiveStack(runtime=runtime, bus=bus, provider=provider, clock=clock)


async def run_live_cycle(
    symbol: str,
    timeframe: str,
    *,
    mode: Literal["paper", "live"] = "paper",
    stack: LiveStack | None = None,
    persist_db: bool = True,
):
    live_stack = stack or await build_live_stack(mode, persist_db=persist_db)
    ts = live_stack.clock.now_processing_time().isoformat()
    correlation_id = f"live_{symbol.replace('/', '')}_{timeframe}_{ts}"
    return await live_stack.runtime.run_cycle(
        symbol,
        timeframe,
        correlation_id=correlation_id,
    )


def default_live_jobs() -> list[tuple[str, str]]:
    app = load_app_yaml_config()
    return [(app.default_symbols[0], app.timeframes[0])]


async def check_connectivity(
    mode: Literal["paper", "live"],
    provider: LiveProvider,
) -> tuple[bool, bool]:
    exchange_ok = provider.ping()
    alerts_ok = False
    if mode == "live":
        from src.events.handlers.telegram_handler import TelegramEventHandler

        alerts_ok = await TelegramEventHandler().ping()
    return exchange_ok, alerts_ok
