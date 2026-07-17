from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from src.core.contracts.event import EventEnvelope
from src.data.csv_provider import CsvDataProvider
from src.events.handlers.event_log_handler import EventLogHandler
from src.runtime.clocks import SimulatedClock
from src.runtime.models import CycleResult
from src.runtime.platform_runtime import PlatformRuntime


@dataclass(frozen=True)
class ValidationConfig:
    symbol: str
    timeframe: str
    start: datetime
    end: datetime
    csv_path: str | None = None
    initial_capital: float = 10000.0


@dataclass
class ValidationResult:
    run_id: str
    config: ValidationConfig
    cycles: list[CycleResult] = field(default_factory=list)
    events: list[EventEnvelope] = field(default_factory=list)
    engine_metrics: dict = field(default_factory=dict)
    outcome_metrics: dict = field(default_factory=dict)
    revision_id: str | None = None
    experiment_id: str | None = None
    experiment_run_id: str | None = None


@dataclass
class ValidationProgressEvent:
    phase: Literal["data", "backtest", "metrics", "persist"]
    message: str
    current: int = 0
    total: int = 0


ValidationProgressCallback = Callable[[ValidationProgressEvent], Awaitable[None] | None]


async def _emit(
    on_progress: ValidationProgressCallback | None,
    event: ValidationProgressEvent,
) -> None:
    if on_progress is None:
        return
    maybe = on_progress(event)
    if maybe is not None:
        await maybe


class ValidationHarness:
    def __init__(
        self,
        runtime: PlatformRuntime,
        data_provider: CsvDataProvider,
        clock: SimulatedClock,
        event_log: EventLogHandler,
        *,
        config: ValidationConfig,
        revision_id: str | None = None,
        experiment_id: str | None = None,
    ) -> None:
        self._runtime = runtime
        self._data_provider = data_provider
        self._clock = clock
        self._event_log = event_log
        self._config = config
        self._revision_id = revision_id
        self._experiment_id = experiment_id

    async def run(
        self,
        *,
        on_progress: ValidationProgressCallback | None = None,
        retain_cycles: bool = True,
    ) -> ValidationResult:
        import uuid

        from src.validation.metrics import (
            EngineMetricsAccumulator,
            compute_engine_metrics,
            compute_outcome_metrics,
        )

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        self._event_log.clear()
        bar_times = self._data_provider.timestamps(
            self._config.symbol,
            self._config.timeframe,
            self._config.start,
            self._config.end,
        )
        from src.validation.lookback import compute_min_lookback_bars

        skip = compute_min_lookback_bars()
        if len(bar_times) <= skip:
            raise ValueError(
                f"Not enough bars in range: need > {skip} for indicator lookback, "
                f"got {len(bar_times)}"
            )
        bar_times = bar_times[skip:]
        total_bars = len(bar_times)
        await _emit(
            on_progress,
            ValidationProgressEvent(
                phase="backtest",
                message=f"Starting backtest over {total_bars} bars…",
                current=0,
                total=total_bars,
            ),
        )
        cycles: list[CycleResult] = []
        engine_acc = EngineMetricsAccumulator()
        for i, bar_time in enumerate(bar_times):
            self._clock.set_event_time(bar_time)
            self._clock.set_processing_time(bar_time + timedelta(seconds=2))
            result = await self._runtime.run_cycle(
                self._config.symbol,
                self._config.timeframe,
                correlation_id=f"val_{i}_{bar_time.isoformat()}",
                revision_id=self._revision_id,
                experiment_id=self._experiment_id,
            )
            if retain_cycles:
                cycles.append(result)
            else:
                engine_acc.observe(result)
            if i % 10 == 0 or i == total_bars - 1:
                await _emit(
                    on_progress,
                    ValidationProgressEvent(
                        phase="backtest",
                        message=(
                            f"Simulating bar {i + 1} of {total_bars} "
                            f"({bar_time.date().isoformat()})…"
                        ),
                        current=i + 1,
                        total=total_bars,
                    ),
                )
                await asyncio.sleep(0)

        await _emit(
            on_progress,
            ValidationProgressEvent(
                phase="backtest",
                message="Closing open positions at end of run…",
                current=total_bars,
                total=total_bars,
            ),
        )
        await self._liquidate_open_positions(bar_times[-1])

        await _emit(
            on_progress,
            ValidationProgressEvent(
                phase="metrics",
                message="Computing engine and outcome metrics…",
                current=total_bars,
                total=total_bars,
            ),
        )

        events = self._event_log.events
        portfolio_id = self._runtime._portfolio_id  # noqa: SLF001
        ending_equity = self._runtime._state_store.get_portfolio(portfolio_id).equity  # noqa: SLF001
        engine_metrics = (
            compute_engine_metrics(cycles, events) if retain_cycles else engine_acc.finalize(events)
        )
        return ValidationResult(
            run_id=run_id,
            config=self._config,
            cycles=cycles,
            events=events,
            engine_metrics=engine_metrics,
            outcome_metrics=compute_outcome_metrics(
                events,
                initial_capital=self._config.initial_capital,
                ending_equity=ending_equity,
            ),
            revision_id=self._revision_id,
            experiment_id=self._experiment_id,
        )

    async def _liquidate_open_positions(self, last_bar_time: datetime) -> None:
        runtime = self._runtime
        execution_engine = runtime._execution_engine  # noqa: SLF001
        if execution_engine is None:
            return

        portfolio_id = runtime._portfolio_id  # noqa: SLF001
        portfolio = runtime._state_store.get_portfolio(portfolio_id)  # noqa: SLF001
        open_for_symbol = [p for p in portfolio.open_positions if p.symbol == self._config.symbol]
        if not open_for_symbol:
            return

        df = self._data_provider.get_latest(
            self._config.symbol,
            self._config.timeframe,
            end=last_bar_time,
        )
        last_row = df.iloc[-1]
        bar = {
            "open": float(last_row["open"]),
            "high": float(last_row["high"]),
            "low": float(last_row["low"]),
            "close": float(last_row["close"]),
            "volume": float(last_row["volume"]),
        }
        processing_time = last_bar_time + timedelta(seconds=2)
        snapshot = runtime._state_store.snapshot(  # noqa: SLF001
            portfolio_id,
            correlation_id=f"val_liquidate_{last_bar_time.isoformat()}",
        )
        result = await execution_engine.liquidate_open_positions(
            bar,
            snapshot,
            symbol=self._config.symbol,
            timeframe=self._config.timeframe,
            correlation_id=f"val_liquidate_{last_bar_time.isoformat()}",
            event_time=last_bar_time,
            processing_time=processing_time,
        )
        for transition in result.transitions:
            runtime._state_store.apply_transition(transition)  # noqa: SLF001
        if result.events:
            await runtime._event_bus.publish_many(list(result.events))  # noqa: SLF001
