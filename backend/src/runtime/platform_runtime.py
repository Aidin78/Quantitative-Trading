from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd

from src.core.contracts.context import MarketContext
from src.core.contracts.data import MarketDataProvider
from src.core.contracts.decision import Decision
from src.core.contracts.event import EventBus, EventEnvelope, EventFamily
from src.core.contracts.features import FeatureSet
from src.core.contracts.provider import SignalProvider
from src.core.contracts.signal import StrategySignal
from src.core.contracts.state import StateSnapshot
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


@dataclass
class _CycleCtx:
    cycle_id: str
    symbol: str
    timeframe: str
    revision_id: str | None
    experiment_id: str | None
    bar: dict[str, float]
    event_time: datetime
    processing_time: datetime
    df: pd.DataFrame
    events: list[EventEnvelope] = field(default_factory=list)
    causation_id: str | None = None
    execution_events: list[EventEnvelope] = field(default_factory=list)


class PlatformRuntime:
    """Orchestrates one market bar from data through decision and optional execution.

    When ``execution_engine`` is set, each ``run_cycle`` follows this bar lifecycle:

    1. **Pre-decision ``evaluate_bar``** — fill pending ``next_open`` entries, then
       check SL/TP/timeout (increments bars held). Transitions are applied before
       the decision snapshot.
    2. **Features / providers / decision** — decision sees the post-exit portfolio.
    3. **Same-bar signal exit** (approved only) — second ``evaluate_bar`` with
       ``increment_bars=False`` so bars-held is not double-counted; closes on
       opposing ``approved_side``.
    4. **``execute``** — open a new position immediately (``fill_at=close|mid``) or
       queue for the next bar's pre-decision eval (``fill_at=next_open``).

    OHLC tradeoff: SL/TP use the full bar high/low while the decision uses that
    bar's close. That is intentionally optimistic vs strict intrabar sequencing
    (stop may fill "before" the close the signal saw).

    ``CycleResult.snapshot`` is decision-time state (after step 1), not post-execute.
    """

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
        persist_features: bool = True,
        emit_events: bool = True,
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
        self._persist_features = persist_features
        self._emit_events = emit_events
        self._signals_day: date | None = None

    async def run_cycle(
        self,
        symbol: str,
        timeframe: str,
        *,
        correlation_id: str | None = None,
        revision_id: str | None = None,
        experiment_id: str | None = None,
    ) -> CycleResult:
        ctx = self._prepare_bar(
            symbol,
            timeframe,
            correlation_id=correlation_id,
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
        await self._pre_decision_evaluate(ctx)
        self._emit_candle_received(ctx)
        feature_set, context = self._build_features(ctx)
        self._maybe_reset_daily_risk(ctx.event_time, ctx.cycle_id)
        # Decision-time snapshot: after pre-decision evaluate_bar, before execute.
        snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=ctx.cycle_id)
        signals = self._collect_provider_signals(ctx, feature_set, context)
        decision = self._decide(ctx, signals, context, snapshot)
        await self._same_bar_exit_and_execute(ctx, decision)

        ctx.events.extend(ctx.execution_events)
        if ctx.events:
            await self._event_bus.publish_many(ctx.events)

        return CycleResult(
            correlation_id=ctx.cycle_id,
            feature_set=feature_set,
            context=context,
            snapshot=snapshot,
            signals=tuple(signals),
            decision=decision,
            events=tuple(ctx.events),
            execution_events=tuple(ctx.execution_events),
        )

    def _prepare_bar(
        self,
        symbol: str,
        timeframe: str,
        *,
        correlation_id: str | None,
        revision_id: str | None,
        experiment_id: str | None,
    ) -> _CycleCtx:
        cycle_id = correlation_id or f"cycle_{uuid.uuid4().hex[:12]}"
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
        return _CycleCtx(
            cycle_id=cycle_id,
            symbol=symbol,
            timeframe=timeframe,
            revision_id=revision_id,
            experiment_id=experiment_id,
            bar=bar,
            event_time=event_time,
            processing_time=processing_time,
            df=df,
        )

    async def _pre_decision_evaluate(self, ctx: _CycleCtx) -> None:
        if self._execution_engine is None:
            return
        pre_snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=ctx.cycle_id)
        bar_eval = await self._execution_engine.evaluate_bar(
            ctx.bar,
            pre_snapshot,
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            correlation_id=ctx.cycle_id,
            event_time=ctx.event_time,
            processing_time=ctx.processing_time,
        )
        for transition in bar_eval.transitions:
            self._state_store.apply_transition(transition)
        ctx.execution_events.extend(bar_eval.events)

    def _emit_candle_received(self, ctx: _CycleCtx) -> None:
        if not self._emit_events:
            return
        candle_event = build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=ctx.event_time,
            processing_time=ctx.processing_time,
            correlation_id=ctx.cycle_id,
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            mode=self._mode,
            payload={
                "open": ctx.bar["open"],
                "high": ctx.bar["high"],
                "low": ctx.bar["low"],
                "close": ctx.bar["close"],
                "volume": ctx.bar["volume"],
            },
            revision_id=ctx.revision_id,
            experiment_id=ctx.experiment_id,
        )
        ctx.events.append(candle_event)
        ctx.causation_id = candle_event.event_id

    def _build_features(self, ctx: _CycleCtx) -> tuple[FeatureSet, MarketContext]:
        feature_set, context = self._feature_builder.build(
            ctx.df,
            ctx.symbol,
            ctx.timeframe,
            processing_time=ctx.processing_time,
            persist=self._persist_features,
        )
        if self._persist_features:
            stored_record = self._feature_store.get(feature_set.feature_set_id)
            if stored_record.market_context != context:
                raise RuntimeError("FeatureStore record does not match built MarketContext")

        if self._emit_events:
            feature_event = build_envelope(
                event_family=EventFamily.MARKET,
                event_type=MarketEventType.FEATURE_SET_BUILT,
                event_time=ctx.event_time,
                processing_time=ctx.processing_time,
                correlation_id=ctx.cycle_id,
                symbol=ctx.symbol,
                timeframe=ctx.timeframe,
                mode=self._mode,
                causation_id=ctx.causation_id,
                payload={
                    "feature_set_id": feature_set.feature_set_id,
                    "feature_version": feature_set.feature_version,
                    "config_hash": feature_set.config_hash,
                    "indicators": feature_set.indicators,
                    "flags": feature_set.flags,
                },
                revision_id=ctx.revision_id,
                experiment_id=ctx.experiment_id,
            )
            ctx.events.append(feature_event)
            ctx.causation_id = feature_event.event_id

            context_event = build_envelope(
                event_family=EventFamily.MARKET,
                event_type=MarketEventType.MARKET_CONTEXT_DERIVED,
                event_time=ctx.event_time,
                processing_time=ctx.processing_time,
                correlation_id=ctx.cycle_id,
                symbol=ctx.symbol,
                timeframe=ctx.timeframe,
                mode=self._mode,
                causation_id=ctx.causation_id,
                payload=context.model_dump(mode="json"),
                revision_id=ctx.revision_id,
                experiment_id=ctx.experiment_id,
            )
            ctx.events.append(context_event)
            ctx.causation_id = context_event.event_id

        return feature_set, context

    def _collect_provider_signals(
        self,
        ctx: _CycleCtx,
        feature_set: FeatureSet,
        context: MarketContext,
    ) -> list[StrategySignal]:
        signals: list[StrategySignal] = []
        for provider in self._providers:
            if not provider.enabled:
                if self._emit_events:
                    skip_event = build_envelope(
                        event_family=EventFamily.SIGNAL,
                        event_type=SignalEventType.PROVIDER_SKIPPED,
                        event_time=ctx.event_time,
                        processing_time=ctx.processing_time,
                        correlation_id=ctx.cycle_id,
                        symbol=ctx.symbol,
                        timeframe=ctx.timeframe,
                        mode=self._mode,
                        causation_id=ctx.causation_id,
                        payload={"provider_id": provider.provider_id, "reason": "disabled"},
                        revision_id=ctx.revision_id,
                        experiment_id=ctx.experiment_id,
                    )
                    ctx.events.append(skip_event)
                continue

            signal = provider.analyze(feature_set, context)
            signals.append(signal)
            if self._emit_events:
                opinion_event = build_envelope(
                    event_family=EventFamily.SIGNAL,
                    event_type=SignalEventType.PROVIDER_OPINION,
                    event_time=ctx.event_time,
                    processing_time=ctx.processing_time,
                    correlation_id=ctx.cycle_id,
                    symbol=ctx.symbol,
                    timeframe=ctx.timeframe,
                    mode=self._mode,
                    causation_id=ctx.causation_id,
                    payload={
                        "provider_id": provider.provider_id,
                        "side": signal.side,
                        "confidence": signal.confidence,
                        "rationale": signal.rationale.model_dump(mode="json"),
                    },
                    revision_id=ctx.revision_id,
                    experiment_id=ctx.experiment_id,
                )
                ctx.events.append(opinion_event)

        return signals

    def _decide(
        self,
        ctx: _CycleCtx,
        signals: list[StrategySignal],
        context: MarketContext,
        snapshot: StateSnapshot,
    ) -> Decision:
        decision = self._decision_engine.process(
            signals,
            context,
            snapshot,
            correlation_id=ctx.cycle_id,
            event_time=ctx.event_time,
            decision_time=ctx.processing_time,
            revision_id=ctx.revision_id,
            experiment_id=ctx.experiment_id,
        )

        if self._emit_events:
            made_event = build_envelope(
                event_family=EventFamily.DECISION,
                event_type=DecisionEventType.DECISION_MADE,
                event_time=ctx.event_time,
                processing_time=ctx.processing_time,
                correlation_id=ctx.cycle_id,
                symbol=ctx.symbol,
                timeframe=ctx.timeframe,
                mode=self._mode,
                causation_id=ctx.causation_id,
                payload={
                    "decision_id": decision.decision_id,
                    "result": decision.result.value,
                    "state_snapshot_id": snapshot.snapshot_id,
                    "decision_log": decision.decision_log.model_dump(mode="json"),
                },
                revision_id=ctx.revision_id,
                experiment_id=ctx.experiment_id,
            )
            ctx.events.append(made_event)
            ctx.causation_id = made_event.event_id

            if decision.is_approved:
                outcome_event = build_envelope(
                    event_family=EventFamily.DECISION,
                    event_type=DecisionEventType.DECISION_APPROVED,
                    event_time=ctx.event_time,
                    processing_time=ctx.processing_time,
                    correlation_id=ctx.cycle_id,
                    symbol=ctx.symbol,
                    timeframe=ctx.timeframe,
                    mode=self._mode,
                    causation_id=ctx.causation_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "state_snapshot_id": snapshot.snapshot_id,
                        "final_signal": decision.final_signal.model_dump(mode="json")
                        if decision.final_signal
                        else None,
                    },
                    revision_id=ctx.revision_id,
                    experiment_id=ctx.experiment_id,
                )
            else:
                outcome_event = build_envelope(
                    event_family=EventFamily.DECISION,
                    event_type=DecisionEventType.DECISION_REJECTED,
                    event_time=ctx.event_time,
                    processing_time=ctx.processing_time,
                    correlation_id=ctx.cycle_id,
                    symbol=ctx.symbol,
                    timeframe=ctx.timeframe,
                    mode=self._mode,
                    causation_id=ctx.causation_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "state_snapshot_id": snapshot.snapshot_id,
                        "rejection_stage": decision.result.rejection_stage,
                        "rejection_reason": decision.result.rejection_reason,
                        "decision_log": decision.decision_log.model_dump(mode="json"),
                    },
                    revision_id=ctx.revision_id,
                    experiment_id=ctx.experiment_id,
                )
            ctx.events.append(outcome_event)
            ctx.causation_id = outcome_event.event_id

            if decision.is_approved and decision.final_signal is not None:
                fs = decision.final_signal
                signal_event = build_envelope(
                    event_family=EventFamily.EXECUTION,
                    event_type=ExecutionEventType.SIGNAL_PUBLISHED,
                    event_time=ctx.event_time,
                    processing_time=ctx.processing_time,
                    correlation_id=ctx.cycle_id,
                    symbol=ctx.symbol,
                    timeframe=ctx.timeframe,
                    mode=self._mode,
                    causation_id=ctx.causation_id,
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
                    revision_id=ctx.revision_id,
                    experiment_id=ctx.experiment_id,
                )
                ctx.events.append(signal_event)

        if decision.is_approved:
            risk_transition = StateTransitionEvent(
                transition_id=f"trans_{uuid.uuid4().hex[:12]}",
                portfolio_id=self._portfolio_id,
                transition_type="risk_updated",
                payload={"signals_today": snapshot.risk.signals_today + 1},
                event_time=ctx.event_time,
                correlation_id=ctx.cycle_id,
            )
            self._state_store.apply_transition(risk_transition)

        return decision

    async def _same_bar_exit_and_execute(self, ctx: _CycleCtx, decision: Decision) -> None:
        if not decision.is_approved or self._execution_engine is None:
            return

        open_positions = self._state_store.get_portfolio(self._portfolio_id).open_positions
        if open_positions and decision.final_signal is not None:
            signal_snapshot = self._state_store.snapshot(
                self._portfolio_id, correlation_id=ctx.cycle_id
            )
            signal_eval = await self._execution_engine.evaluate_bar(
                ctx.bar,
                signal_snapshot,
                symbol=ctx.symbol,
                timeframe=ctx.timeframe,
                correlation_id=ctx.cycle_id,
                event_time=ctx.event_time,
                processing_time=ctx.processing_time,
                approved_side=decision.final_signal.side,
                increment_bars=False,
            )
            for transition in signal_eval.transitions:
                self._state_store.apply_transition(transition)
            ctx.execution_events.extend(signal_eval.events)

        exec_snapshot = self._state_store.snapshot(self._portfolio_id, correlation_id=ctx.cycle_id)
        exec_result = await self._execution_engine.execute(
            decision,
            exec_snapshot,
            ctx.bar,
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            correlation_id=ctx.cycle_id,
            processing_time=ctx.processing_time,
        )
        for transition in exec_result.transitions:
            self._state_store.apply_transition(transition)
        ctx.execution_events.extend(exec_result.events)

    def _maybe_reset_daily_risk(self, event_time: datetime, cycle_id: str) -> None:
        current_day = event_time.date()
        if self._signals_day is None:
            self._signals_day = current_day
            return
        if current_day == self._signals_day:
            return
        self._signals_day = current_day
        risk = self._state_store.get_risk(self._portfolio_id)
        if risk.signals_today == 0 and risk.daily_pnl == 0.0 and risk.daily_drawdown_pct == 0.0:
            return
        reset_transition = StateTransitionEvent(
            transition_id=f"trans_{uuid.uuid4().hex[:12]}",
            portfolio_id=self._portfolio_id,
            transition_type="risk_updated",
            payload={"signals_today": 0, "daily_pnl": 0.0, "daily_drawdown_pct": 0.0},
            event_time=event_time,
            correlation_id=cycle_id,
        )
        self._state_store.apply_transition(reset_transition)

    @staticmethod
    def _resolve_event_time(df: pd.DataFrame, last_row: Any) -> datetime:
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
