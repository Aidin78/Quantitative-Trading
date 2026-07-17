from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from src.core.contracts.decision import Decision
from src.core.contracts.event import EventFamily
from src.core.contracts.execution import FillModel, Order, OrderIntent
from src.core.contracts.state import StateSnapshot
from src.core.contracts.time import Clock
from src.events.envelopes import ExecutionEventType, build_envelope
from src.execution.config import ValidationExecutionConfig, load_validation_execution_config
from src.execution.engine import ExecutionResult
from src.execution.risk_gate import ExecutionRiskGate
from src.execution.simulated_events import execution_failed, filter_events
from src.execution.simulated_exits import check_exit
from src.execution.simulated_pending import PendingEntry, process_pending_entries
from src.execution.simulated_positions import close_position, open_position
from src.execution.simulated_pricing import fill_price, position_size
from src.state.transitions import StateTransitionEvent

# Compatibility alias for tests / internal references.
_PendingEntry = PendingEntry


class SimulatedExecutionEngine:
    _SCORE_OUTCOME_TYPES = frozenset(
        {
            ExecutionEventType.ORDER_REJECTED,
            ExecutionEventType.POSITION_OPENED,
            ExecutionEventType.POSITION_CLOSED,
        }
    )

    def __init__(
        self,
        fill_model: FillModel,
        clock: Clock,
        *,
        risk_gate: ExecutionRiskGate | None = None,
        config: ValidationExecutionConfig | None = None,
        mode: Literal["validation", "live", "paper", "replay"] = "validation",
        emit_events: bool = True,
    ) -> None:
        self._fill_model = fill_model
        self._clock = clock
        self._risk_gate = risk_gate or ExecutionRiskGate()
        self._config = config or load_validation_execution_config()
        self._mode = mode
        self._emit_events = emit_events
        self._position_bars: dict[str, int] = {}
        self._pending_entries: list[PendingEntry] = []
        self._position_orders: dict[str, str] = {}

    def _filter_events(self, events: list) -> tuple:
        return filter_events(self, events)

    def _execution_failed(
        self,
        event_time: datetime,
        processing_time: datetime,
        correlation_id: str,
        symbol: str,
        timeframe: str,
        *,
        error: str,
        stage: str,
    ):
        return execution_failed(
            self,
            event_time,
            processing_time,
            correlation_id,
            symbol,
            timeframe,
            error=error,
            stage=stage,
        )

    def _position_size(self, snapshot: StateSnapshot, entry: float, stop_loss: float) -> float:
        return position_size(self, snapshot, entry, stop_loss)

    def _fill_price(self, bar: dict[str, Any], side: str, *, use_next_open: bool = False) -> float:
        return fill_price(self, bar, side, use_next_open=use_next_open)

    def _check_exit(
        self,
        position,
        bar: dict[str, Any],
        bars_held: int,
        *,
        approved_side: Literal["BUY", "SELL"] | None = None,
        check_timeout: bool = True,
    ) -> tuple[str | None, float]:
        return check_exit(
            self,
            position,
            bar,
            bars_held,
            approved_side=approved_side,
            check_timeout=check_timeout,
        )

    def _open_position(self, **kwargs):
        return open_position(self, **kwargs)

    def _close_position(self, **kwargs):
        return close_position(self, **kwargs)

    async def _process_pending_entries(self, *args, **kwargs) -> ExecutionResult:
        return await process_pending_entries(self, *args, **kwargs)

    async def execute(
        self,
        decision: Decision,
        snapshot: StateSnapshot,
        bar: dict[str, Any],
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        processing_time: datetime,
    ) -> ExecutionResult:
        if not decision.is_approved or decision.final_signal is None:
            return ExecutionResult(events=(), transitions=())

        signal = decision.final_signal
        quantity = self._position_size(snapshot, signal.entry_price, signal.stop_loss)
        if quantity <= 0:
            return ExecutionResult(
                events=self._filter_events(
                    [
                        self._execution_failed(
                            decision.event_time,
                            processing_time,
                            correlation_id,
                            symbol,
                            timeframe,
                            error="invalid_position_size",
                            stage="sizing",
                        )
                    ]
                ),
                transitions=(),
            )

        intent = OrderIntent(
            intent_id=f"intent_{uuid.uuid4().hex[:12]}",
            decision_id=decision.decision_id,
            correlation_id=correlation_id,
            symbol=symbol,
            side=signal.side,
            quantity=quantity,
            limit_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            state_snapshot_id=snapshot.snapshot_id,
            revision_id=decision.revision_id,
            experiment_id=decision.experiment_id,
        )

        events: list = []
        transitions: list[StateTransitionEvent] = []
        causation_id: str | None = None

        if self._emit_events:
            intent_event = build_envelope(
                event_family=EventFamily.EXECUTION,
                event_type=ExecutionEventType.ORDER_INTENT_CREATED,
                event_time=decision.event_time,
                processing_time=processing_time,
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                payload={"intent": intent.model_dump(mode="json")},
            )
            events.append(intent_event)
            causation_id = intent_event.event_id

        risk_result = self._risk_gate.check(intent, snapshot)
        if not risk_result.passed:
            reject_event = build_envelope(
                event_family=EventFamily.EXECUTION,
                event_type=ExecutionEventType.ORDER_REJECTED,
                event_time=decision.event_time,
                processing_time=processing_time,
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={"reason": risk_result.reason, "stage": "pre_trade"},
            )
            events.append(reject_event)
            return ExecutionResult(events=self._filter_events(events), transitions=())

        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:12]}",
            intent_id=intent.intent_id,
            status="submitted",
            submitted_at=processing_time,
            venue="simulator",
        )
        if self._emit_events:
            submit_event = build_envelope(
                event_family=EventFamily.EXECUTION,
                event_type=ExecutionEventType.ORDER_SUBMITTED,
                event_time=decision.event_time,
                processing_time=processing_time,
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={
                    "order": order.model_dump(mode="json"),
                    "venue": "simulator",
                    "decision_id": decision.decision_id,
                },
            )
            events.append(submit_event)
            causation_id = submit_event.event_id

            ack_event = build_envelope(
                event_family=EventFamily.EXECUTION,
                event_type=ExecutionEventType.ORDER_ACKNOWLEDGED,
                event_time=decision.event_time,
                processing_time=processing_time,
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                mode=self._mode,
                causation_id=causation_id,
                payload={"order_id": order.order_id, "venue": "simulator"},
            )
            events.append(ack_event)
            causation_id = ack_event.event_id

        position_side: Literal["LONG", "SHORT"] = "LONG" if signal.side == "BUY" else "SHORT"

        if self._fill_model.fill_at == "next_open":
            self._pending_entries.append(
                PendingEntry(
                    order=order,
                    intent=intent,
                    quantity=quantity,
                    side=signal.side,
                    position_side=position_side,
                    symbol=symbol,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    decision_event_time=decision.event_time,
                    portfolio_id=snapshot.portfolio.portfolio_id,
                )
            )
            return ExecutionResult(events=self._filter_events(events), transitions=())

        fill_events, transition = open_position(
            self,
            order=order,
            quantity=quantity,
            side=signal.side,
            position_side=position_side,
            symbol=symbol,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            bar=bar,
            snapshot=snapshot,
            correlation_id=correlation_id,
            timeframe=timeframe,
            event_time=decision.event_time,
            processing_time=processing_time,
            causation_id=causation_id,
        )
        events.extend(fill_events)
        if transition:
            transitions.append(transition)

        return ExecutionResult(events=self._filter_events(events), transitions=tuple(transitions))

    async def evaluate_bar(
        self,
        bar: dict[str, Any],
        snapshot: StateSnapshot,
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        event_time: datetime,
        processing_time: datetime,
        approved_side: Literal["BUY", "SELL"] | None = None,
        increment_bars: bool = True,
    ) -> ExecutionResult:
        """Evaluate fills and exits for one bar; returns transitions (no direct store writes).

        With ``increment_bars=True`` (pre-decision path): process pending ``next_open``
        entries, increment bars held, then check SL/TP/timeout against bar H/L/close.

        With ``increment_bars=False`` (same-bar signal-exit path): skip pending fills and
        bar increment; if ``approved_side`` opposes the open position, exit at close.
        """
        events: list = []
        transitions: list[StateTransitionEvent] = []

        if increment_bars:
            pending_result = await process_pending_entries(
                self,
                bar,
                snapshot,
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=correlation_id,
                event_time=event_time,
                processing_time=processing_time,
            )
            events.extend(pending_result.events)
            transitions.extend(pending_result.transitions)

        for position in snapshot.portfolio.open_positions:
            if position.symbol != symbol:
                continue

            bars_held = self._position_bars.get(position.position_id, 0)
            if increment_bars:
                bars_held += 1
                self._position_bars[position.position_id] = bars_held

            exit_reason, exit_price = check_exit(
                self,
                position,
                bar,
                bars_held,
                approved_side=approved_side,
                check_timeout=increment_bars,
            )
            if exit_reason is None:
                continue

            close_events, transition = close_position(
                self,
                position=position,
                exit_price=exit_price,
                exit_reason=exit_reason,
                snapshot=snapshot,
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=correlation_id,
                event_time=event_time,
                processing_time=processing_time,
            )
            events.extend(close_events)
            transitions.append(transition)

        return ExecutionResult(events=self._filter_events(events), transitions=tuple(transitions))

    async def liquidate_open_positions(
        self,
        bar: dict[str, Any],
        snapshot: StateSnapshot,
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        event_time: datetime,
        processing_time: datetime,
    ) -> ExecutionResult:
        events: list = []
        transitions: list[StateTransitionEvent] = []
        exit_price = float(bar["close"])

        for position in snapshot.portfolio.open_positions:
            if position.symbol != symbol:
                continue
            close_events, transition = close_position(
                self,
                position=position,
                exit_price=exit_price,
                exit_reason="end_of_run",
                snapshot=snapshot,
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=correlation_id,
                event_time=event_time,
                processing_time=processing_time,
            )
            events.extend(close_events)
            transitions.append(transition)

        return ExecutionResult(events=tuple(events), transitions=tuple(transitions))
