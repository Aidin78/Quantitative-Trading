from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

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

    async def run(self) -> ValidationResult:
        import uuid

        from src.validation.metrics import compute_engine_metrics, compute_outcome_metrics

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
        cycles: list[CycleResult] = []
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
            cycles.append(result)

        events = self._event_log.events
        return ValidationResult(
            run_id=run_id,
            config=self._config,
            cycles=cycles,
            events=events,
            engine_metrics=compute_engine_metrics(cycles, events),
            outcome_metrics=compute_outcome_metrics(events),
            revision_id=self._revision_id,
            experiment_id=self._experiment_id,
        )
