from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from src.core.contracts.data import MarketDataProvider
from src.core.contracts.event import EventBus, EventEnvelope, EventFamily
from src.core.contracts.provider import SignalProvider
from src.core.contracts.signal import StrategySignal
from src.core.contracts.time import Clock
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import (
    DecisionEventType,
    ExecutionEventType,
    MarketEventType,
    SignalEventType,
    build_envelope,
)
from src.execution.engine import ExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import FeatureStore
from src.runtime.models import CycleResult
from src.state.store import StateStore
from src.state.transitions import StateTransitionEvent


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
        event_bus: EventBus,
        clock: Clock,
        portfolio_id: str,
        mode: Literal["validation", "live", "paper", "replay"] = "validation",
        execution_engine: ExecutionEngine | None = None,
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
        self._execution_engine = execution_engine

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

        bar = {
            "open": float(last_row["open"]),
            "high": float(last_row["high"]),
            "low": float(last_row["low"]),
            "close": float(last_row["close"]),
            "volume": float(last_row["volume"]),
        }

        execution_events: list[EventEnvelope] = []

        if self._execution_engine is not None:
            pre_snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=cycle_id)
            bar_eval = await self._execution_engine.evaluate_bar(
                bar,
                pre_snapshot,
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=cycle_id,
                event_time=event_time,
                processing_time=processing_time,
            )
            for transition in bar_eval.transitions:
                self._state_store.apply_transition(transition)
            execution_events.extend(bar_eval.events)

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
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
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
        causation_id = outcome_event.event_id

        if decision.is_approved and decision.final_signal is not None:
            fs = decision.final_signal
            signal_event = build_envelope(
                event_family=EventFamily.EXECUTION,
                event_type=ExecutionEventType.SIGNAL_PUBLISHED,
                event_time=event_time,
                processing_time=processing_time,
                correlation_id=cycle_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={
                    "decision_id": decision.decision_id,
                    "side": fs.side,
                    "entry_price": fs.entry_price,
                    "stop_loss": fs.stop_loss,
                    "take_profit": fs.take_profit,
                    "confidence": fs.confidence,
                    "risk_reward": fs.risk_reward,
                    "provider_ids": list(fs.contributing_providers),
                },
                revision_id=revision_id,
                experiment_id=experiment_id,
            )
            events.append(signal_event)

        if decision.is_approved:
            risk_transition = StateTransitionEvent(
                transition_id=f"trans_{uuid.uuid4().hex[:12]}",
                portfolio_id=self._portfolio_id,
                transition_type="risk_updated",
                payload={"signals_today": snapshot.risk.signals_today + 1},
                event_time=event_time,
                correlation_id=cycle_id,
            )
            self._state_store.apply_transition(risk_transition)

        if decision.is_approved and self._execution_engine is not None:
            open_positions = self._state_store.get_portfolio(self._portfolio_id).open_positions
            if open_positions and decision.final_signal is not None:
                signal_snapshot = self._state_store.snapshot(
                    self._portfolio_id, correlation_id=cycle_id
                )
                signal_eval = await self._execution_engine.evaluate_bar(
                    bar,
                    signal_snapshot,
                    symbol=symbol,
                    timeframe=timeframe,
                    correlation_id=cycle_id,
                    event_time=event_time,
                    processing_time=processing_time,
                    approved_side=decision.final_signal.side,
                    increment_bars=False,
                )
                for transition in signal_eval.transitions:
                    self._state_store.apply_transition(transition)
                execution_events.extend(signal_eval.events)

            exec_snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=cycle_id)
            exec_result = await self._execution_engine.execute(
                decision,
                exec_snapshot,
                bar,
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=cycle_id,
                processing_time=processing_time,
            )
            for transition in exec_result.transitions:
                self._state_store.apply_transition(transition)
            execution_events.extend(exec_result.events)

        events.extend(execution_events)
        await self._event_bus.publish_many(events)

        return CycleResult(
            correlation_id=cycle_id,
            feature_set=feature_set,
            context=context,
            snapshot=snapshot,
            signals=tuple(signals),
            decision=decision,
            events=tuple(events),
            execution_events=tuple(execution_events),
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
