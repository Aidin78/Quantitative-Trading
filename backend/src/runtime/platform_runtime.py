from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Protocol

from src.core.contracts.event import EventEnvelope, EventFamily
from src.core.contracts.provider import SignalProvider
from src.core.contracts.signal import StrategySignal
from src.core.contracts.time import Clock
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import (
    DecisionEventType,
    MarketEventType,
    SignalEventType,
    build_envelope,
)
from src.events.in_memory_bus import InMemoryEventBus
from src.features.builder import DefaultFeatureBuilder
from src.features.store import FeatureStore
from src.runtime.models import CycleResult
from src.state.store import StateStore


class MarketDataProvider(Protocol):
    def get_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        end: datetime | None = None,
    ): ...


class PlatformRuntime:
    def __init__(
        self,
        *,
        data_provider: MarketDataProvider,
        feature_builder: DefaultFeatureBuilder,
        feature_store: FeatureStore,
        state_store: StateStore,
        providers: list[SignalProvider],
        decision_engine: DecisionEngine,
        event_bus: InMemoryEventBus,
        clock: Clock,
        portfolio_id: str,
        mode: Literal["validation", "live", "paper", "replay"] = "validation",
    ) -> None:
        self._data_provider = data_provider
        self._feature_store = feature_store
        self._feature_builder = feature_builder
        if self._feature_builder.store is None:
            self._feature_builder.bind_store(feature_store)
        elif self._feature_builder.store is not feature_store:
            raise ValueError("feature_builder and feature_store must share the same store instance")
        self._state_store = state_store
        self._providers = providers
        self._decision_engine = decision_engine
        self._event_bus = event_bus
        self._clock = clock
        self._portfolio_id = portfolio_id
        self._mode = mode

    async def run_cycle(
        self,
        symbol: str,
        timeframe: str,
        *,
        correlation_id: str | None = None,
        revision_id: str | None = None,
        experiment_id: str | None = None,
    ) -> CycleResult:
        cycle_id = correlation_id or f"cycle_{uuid.uuid4().hex[:12]}"
        events: list[EventEnvelope] = []
        causation_id: str | None = None

        end = self._clock.now_event_time()
        df = self._data_provider.get_latest(symbol, timeframe, end=end)
        last_row = df.iloc[-1]
        event_time = self._resolve_event_time(df, last_row)
        processing_time = self._clock.now_processing_time()
        if hasattr(self._clock, "set_event_time"):
            self._clock.set_event_time(event_time)  # type: ignore[attr-defined]

        candle_event = build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=cycle_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            payload={
                "open": float(last_row["open"]),
                "high": float(last_row["high"]),
                "low": float(last_row["low"]),
                "close": float(last_row["close"]),
                "volume": float(last_row["volume"]),
            },
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
        events.append(candle_event)
        causation_id = candle_event.event_id

        feature_set, context = self._feature_builder.build(
            df,
            symbol,
            timeframe,
            processing_time=processing_time,
            persist=True,
        )
        stored_record = self._feature_store.get(feature_set.feature_set_id)
        if stored_record.market_context != context:
            raise RuntimeError("FeatureStore record does not match built MarketContext")

        feature_event = build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.FEATURE_SET_BUILT,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=cycle_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=causation_id,
            payload={
                "feature_set_id": feature_set.feature_set_id,
                "feature_version": feature_set.feature_version,
                "config_hash": feature_set.config_hash,
                "indicators": feature_set.indicators,
                "flags": feature_set.flags,
            },
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
        events.append(feature_event)
        causation_id = feature_event.event_id

        context_event = build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.MARKET_CONTEXT_DERIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=cycle_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=causation_id,
            payload=context.model_dump(mode="json"),
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
        events.append(context_event)
        causation_id = context_event.event_id

        snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=cycle_id)

        signals: list[StrategySignal] = []
        for provider in self._providers:
            if not provider.enabled:
                skip_event = build_envelope(
                    event_family=EventFamily.SIGNAL,
                    event_type=SignalEventType.PROVIDER_SKIPPED,
                    event_time=event_time,
                    processing_time=processing_time,
                    correlation_id=cycle_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    mode=self._mode,
                    causation_id=causation_id,
                    payload={"provider_id": provider.provider_id, "reason": "disabled"},
                    revision_id=revision_id,
                    experiment_id=experiment_id,
                )
                events.append(skip_event)
                continue

            signal = provider.analyze(feature_set, context)
            signals.append(signal)
            opinion_event = build_envelope(
                event_family=EventFamily.SIGNAL,
                event_type=SignalEventType.PROVIDER_OPINION,
                event_time=event_time,
                processing_time=processing_time,
                correlation_id=cycle_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={
                    "provider_id": provider.provider_id,
                    "side": signal.side,
                    "confidence": signal.confidence,
                    "rationale": signal.rationale.model_dump(mode="json"),
                },
                revision_id=revision_id,
                experiment_id=experiment_id,
            )
            events.append(opinion_event)

        decision = self._decision_engine.process(
            signals,
            context,
            snapshot,
            correlation_id=cycle_id,
            event_time=event_time,
            decision_time=processing_time,
            revision_id=revision_id,
            experiment_id=experiment_id,
        )

        made_event = build_envelope(
            event_family=EventFamily.DECISION,
            event_type=DecisionEventType.DECISION_MADE,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=cycle_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=causation_id,
            payload={
                "decision_id": decision.decision_id,
                "result": decision.result.value,
                "state_snapshot_id": snapshot.snapshot_id,
                "decision_log": decision.decision_log.model_dump(mode="json"),
            },
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
        events.append(made_event)
        causation_id = made_event.event_id

        if decision.is_approved:
            outcome_event = build_envelope(
                event_family=EventFamily.DECISION,
                event_type=DecisionEventType.DECISION_APPROVED,
                event_time=event_time,
                processing_time=processing_time,
                correlation_id=cycle_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={
                    "decision_id": decision.decision_id,
                    "state_snapshot_id": snapshot.snapshot_id,
                    "final_signal": decision.final_signal.model_dump(mode="json")
                    if decision.final_signal
                    else None,
                },
                revision_id=revision_id,
                experiment_id=experiment_id,
            )
        else:
            outcome_event = build_envelope(
                event_family=EventFamily.DECISION,
                event_type=DecisionEventType.DECISION_REJECTED,
                event_time=event_time,
                processing_time=processing_time,
                correlation_id=cycle_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={
                    "decision_id": decision.decision_id,
                    "state_snapshot_id": snapshot.snapshot_id,
                    "rejection_stage": decision.result.rejection_stage,
                    "rejection_reason": decision.result.rejection_reason,
                    "decision_log": decision.decision_log.model_dump(mode="json"),
                },
                revision_id=revision_id,
                experiment_id=experiment_id,
            )
        events.append(outcome_event)

        await self._event_bus.publish_many(events)

        return CycleResult(
            correlation_id=cycle_id,
            feature_set=feature_set,
            context=context,
            snapshot=snapshot,
            signals=tuple(signals),
            decision=decision,
            events=tuple(events),
        )

    @staticmethod
    def _resolve_event_time(df, last_row) -> datetime:  # noqa: ANN001
        if "timestamp" in df.columns:
            ts = last_row["timestamp"]
            if hasattr(ts, "to_pydatetime"):
                return ts.to_pydatetime()
            return ts
        if hasattr(df.index, "tz"):
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                return ts.to_pydatetime()
            return ts
        raise ValueError("Cannot resolve event_time from OHLCV data")
