from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from src.core.contracts.decision import Decision
from src.core.contracts.event import EventFamily
from src.core.contracts.execution import Fill, FillModel, Order, OrderIntent
from src.core.contracts.state import PositionState, StateSnapshot
from src.core.contracts.time import Clock
from src.events.envelopes import ExecutionEventType, build_envelope
from src.execution.config import ValidationExecutionConfig, load_validation_execution_config
from src.execution.engine import ExecutionResult
from src.execution.risk_gate import ExecutionRiskGate
from src.state.transitions import StateTransitionEvent


@dataclass(frozen=True)
class _PendingEntry:
    order: Order
    intent: OrderIntent
    quantity: float
    side: Literal["BUY", "SELL"]
    position_side: Literal["LONG", "SHORT"]
    symbol: str
    stop_loss: float
    take_profit: float
    decision_event_time: datetime
    portfolio_id: str


class SimulatedExecutionEngine:
    def __init__(
        self,
        fill_model: FillModel,
        clock: Clock,
        *,
        risk_gate: ExecutionRiskGate | None = None,
        config: ValidationExecutionConfig | None = None,
        mode: Literal["validation", "live", "paper", "replay"] = "validation",
    ) -> None:
        self._fill_model = fill_model
        self._clock = clock
        self._risk_gate = risk_gate or ExecutionRiskGate()
        self._config = config or load_validation_execution_config()
        self._mode = mode
        self._position_bars: dict[str, int] = {}
        self._pending_entries: list[_PendingEntry] = []
        self._position_orders: dict[str, str] = {}

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
                events=(
                    self._execution_failed(
                        decision.event_time,
                        processing_time,
                        correlation_id,
                        symbol,
                        timeframe,
                        error="invalid_position_size",
                        stage="sizing",
                    ),
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
            return ExecutionResult(events=tuple(events), transitions=())

        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:12]}",
            intent_id=intent.intent_id,
            status="submitted",
            submitted_at=processing_time,
            venue="simulator",
        )
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
                _PendingEntry(
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
            return ExecutionResult(events=tuple(events), transitions=())

        fill_events, transition = self._open_position(
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

        return ExecutionResult(events=tuple(events), transitions=tuple(transitions))

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
        events: list = []
        transitions: list[StateTransitionEvent] = []

        if increment_bars:
            pending_result = await self._process_pending_entries(
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

            exit_reason, exit_price = self._check_exit(
                position,
                bar,
                bars_held,
                approved_side=approved_side,
                check_timeout=increment_bars,
            )
            if exit_reason is None:
                continue

            close_events, transition = self._close_position(
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

        return ExecutionResult(events=tuple(events), transitions=tuple(transitions))

    async def _process_pending_entries(
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
        remaining: list[_PendingEntry] = []

        for pending in self._pending_entries:
            if pending.symbol != symbol:
                remaining.append(pending)
                continue

            fill_events, transition = self._open_position(
                order=pending.order,
                quantity=pending.quantity,
                side=pending.side,
                position_side=pending.position_side,
                symbol=pending.symbol,
                stop_loss=pending.stop_loss,
                take_profit=pending.take_profit,
                bar=bar,
                snapshot=snapshot,
                correlation_id=correlation_id,
                timeframe=timeframe,
                event_time=event_time,
                processing_time=processing_time,
                causation_id=None,
                use_next_open=True,
            )
            events.extend(fill_events)
            if transition:
                transitions.append(transition)

        self._pending_entries = remaining
        return ExecutionResult(events=tuple(events), transitions=tuple(transitions))

    def _open_position(
        self,
        *,
        order: Order,
        quantity: float,
        side: str,
        position_side: Literal["LONG", "SHORT"],
        symbol: str,
        stop_loss: float,
        take_profit: float,
        bar: dict[str, Any],
        snapshot: StateSnapshot,
        correlation_id: str,
        timeframe: str,
        event_time: datetime,
        processing_time: datetime,
        causation_id: str | None,
        use_next_open: bool = False,
    ) -> tuple[list, StateTransitionEvent | None]:
        fill_price = self._fill_price(bar, side, use_next_open=use_next_open)
        fee = fill_price * quantity * self._fill_model.fee_bps / 10_000
        fill = Fill(
            fill_id=f"fill_{uuid.uuid4().hex[:12]}",
            order_id=order.order_id,
            price=fill_price,
            quantity=quantity,
            fee=fee,
            slippage_bps=self._fill_model.slippage_bps,
            fill_time=event_time,
        )

        fill_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.FILL_RECEIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=causation_id,
            payload={
                "fill": fill.model_dump(mode="json"),
                "fill_model_id": self._fill_model.model_id,
            },
        )

        position_id = f"pos_{uuid.uuid4().hex[:12]}"
        position = PositionState(
            position_id=position_id,
            symbol=symbol,
            side=position_side,
            quantity=quantity,
            entry_price=fill_price,
            entry_time=event_time,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        self._position_bars[position_id] = 0
        self._position_orders[position_id] = order.order_id

        open_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_OPENED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=fill_event.event_id,
            payload={
                "position_id": position_id,
                "entry_fill_id": fill.fill_id,
                "position": position.model_dump(mode="json"),
            },
        )

        transition = StateTransitionEvent(
            transition_id=f"trans_{uuid.uuid4().hex[:12]}",
            portfolio_id=snapshot.portfolio.portfolio_id,
            transition_type="position_opened",
            payload={
                "position": position.model_dump(mode="json"),
                "fill": fill.model_dump(mode="json"),
                "cost": fill_price * quantity + fee,
            },
            event_time=event_time,
            correlation_id=correlation_id,
        )
        return [fill_event, open_event], transition

    def _close_position(
        self,
        *,
        position: PositionState,
        exit_price: float,
        exit_reason: str,
        snapshot: StateSnapshot,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        event_time: datetime,
        processing_time: datetime,
    ) -> tuple[list, StateTransitionEvent]:
        fill_price = exit_price
        fee = fill_price * position.quantity * self._fill_model.fee_bps / 10_000
        order_id = self._position_orders.get(position.position_id, f"ord_{position.position_id}")
        fill = Fill(
            fill_id=f"fill_{uuid.uuid4().hex[:12]}",
            order_id=order_id,
            price=fill_price,
            quantity=position.quantity,
            fee=fee,
            slippage_bps=self._fill_model.slippage_bps,
            fill_time=event_time,
        )

        if position.side == "LONG":
            pnl = (fill_price - position.entry_price) * position.quantity - fee
        else:
            pnl = (position.entry_price - fill_price) * position.quantity - fee

        fill_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.FILL_RECEIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            payload={
                "fill": fill.model_dump(mode="json"),
                "fill_model_id": self._fill_model.model_id,
                "exit": True,
            },
        )

        close_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            causation_id=fill_event.event_id,
            payload={
                "position_id": position.position_id,
                "exit_reason": exit_reason,
                "exit_price": fill_price,
                "pnl": pnl,
                "fill_id": fill.fill_id,
                "entry_price": position.entry_price,
                "side": position.side,
                "quantity": position.quantity,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "bars_held": self._position_bars.get(position.position_id, 0),
            },
        )

        transition = StateTransitionEvent(
            transition_id=f"trans_{uuid.uuid4().hex[:12]}",
            portfolio_id=snapshot.portfolio.portfolio_id,
            transition_type="position_closed",
            payload={
                "position_id": position.position_id,
                "fill": fill.model_dump(mode="json"),
                "pnl": pnl,
                "exit_reason": exit_reason,
            },
            event_time=event_time,
            correlation_id=correlation_id,
        )
        self._position_bars.pop(position.position_id, None)
        self._position_orders.pop(position.position_id, None)
        return [fill_event, close_event], transition

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
        return build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.EXECUTION_FAILED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=self._mode,
            payload={"error": error, "stage": stage},
        )

    def _position_size(self, snapshot: StateSnapshot, entry: float, stop_loss: float) -> float:
        portfolio = snapshot.portfolio
        risk = snapshot.risk
        risk_amount = portfolio.equity * self._config.risk_pct_per_trade / 100
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit <= 0 or entry <= 0:
            return 0.0
        risk_based_qty = risk_amount / risk_per_unit

        max_cash_qty = portfolio.cash / entry if portfolio.cash > 0 else 0.0
        remaining_exposure = max(
            0.0,
            risk.limits.max_exposure_pct - risk.open_exposure_pct,
        )
        max_exposure_qty = (remaining_exposure / 100 * portfolio.equity) / entry

        quantity = min(risk_based_qty, max_cash_qty, max_exposure_qty)
        return round(quantity, 8) if quantity > 0 else 0.0

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
            close_events, transition = self._close_position(
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

    def _fill_price(self, bar: dict[str, Any], side: str, *, use_next_open: bool = False) -> float:
        if use_next_open or self._fill_model.fill_at == "next_open":
            base = float(bar["open"])
        elif self._fill_model.fill_at == "mid":
            base = (float(bar["high"]) + float(bar["low"])) / 2
        else:
            base = float(bar["close"])

        slip = self._fill_model.slippage_bps / 10_000
        if side == "BUY":
            return base * (1 + slip)
        return base * (1 - slip)

    def _check_exit(
        self,
        position: PositionState,
        bar: dict[str, Any],
        bars_held: int,
        *,
        approved_side: Literal["BUY", "SELL"] | None = None,
        check_timeout: bool = True,
    ) -> tuple[str | None, float]:
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])

        if approved_side is not None and not check_timeout:
            if position.side == "LONG" and approved_side == "SELL":
                return "signal", close
            if position.side == "SHORT" and approved_side == "BUY":
                return "signal", close
            return None, 0.0

        if position.side == "LONG":
            if position.stop_loss is not None and low <= position.stop_loss:
                return "stop_loss", position.stop_loss
            if position.take_profit is not None and high >= position.take_profit:
                return "take_profit", position.take_profit
        else:
            if position.stop_loss is not None and high >= position.stop_loss:
                return "stop_loss", position.stop_loss
            if position.take_profit is not None and low <= position.take_profit:
                return "take_profit", position.take_profit

        if check_timeout and bars_held >= self._config.max_bars_in_trade:
            return "timeout", close

        return None, 0.0
