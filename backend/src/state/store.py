from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, Protocol

from src.core.contracts.state import (
    PortfolioState,
    PositionState,
    RiskLimits,
    RiskState,
    StateSnapshot,
)
from src.state.transitions import StateTransitionEvent


class StateStore(Protocol):
    def get_portfolio(self, portfolio_id: str) -> PortfolioState: ...

    def get_risk(self, portfolio_id: str) -> RiskState: ...

    def snapshot(
        self, portfolio_id: str, *, correlation_id: str | None = None
    ) -> StateSnapshot: ...

    def apply_transition(self, event: StateTransitionEvent) -> StateSnapshot: ...


class InMemoryStateStore:
    def __init__(
        self,
        *,
        portfolio_id: str = "portfolio_default",
        mode: Literal["validation", "live", "paper", "replay"] = "validation",
        initial_cash: float = 10000.0,
        limits: RiskLimits | None = None,
    ) -> None:
        self._portfolio_id = portfolio_id
        self._limits = limits or RiskLimits(
            max_daily_drawdown_pct=5.0,
            max_open_positions=3,
            max_exposure_pct=50.0,
        )
        now = datetime.now(UTC)
        self._portfolio = PortfolioState(
            portfolio_id=portfolio_id,
            mode=mode,
            cash=initial_cash,
            equity=initial_cash,
            open_positions=(),
            version=1,
            as_of_event_time=now,
            as_of_processing_time=now,
        )
        self._risk = RiskState(
            risk_state_id=f"risk_{portfolio_id}",
            portfolio_id=portfolio_id,
            limits=self._limits,
            version=1,
            as_of_event_time=now,
        )
        self._snapshots: dict[str, StateSnapshot] = {}

    def get_portfolio(self, portfolio_id: str) -> PortfolioState:
        self._assert_portfolio(portfolio_id)
        return self._portfolio

    def get_risk(self, portfolio_id: str) -> RiskState:
        self._assert_portfolio(portfolio_id)
        return self._risk

    def snapshot(self, portfolio_id: str, *, correlation_id: str | None = None) -> StateSnapshot:
        self._assert_portfolio(portfolio_id)
        now = datetime.now(UTC)
        snap = StateSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            portfolio=self._portfolio,
            risk=self._risk,
            version=self._portfolio.version,
            created_at=now,
            correlation_id=correlation_id,
        )
        self._snapshots[snap.snapshot_id] = snap
        return snap

    def apply_transition(self, event: StateTransitionEvent) -> StateSnapshot:
        self._assert_portfolio(event.portfolio_id)
        if event.transition_type == "position_opened":
            self._apply_position_opened(event)
        elif event.transition_type == "position_closed":
            self._apply_position_closed(event)
        elif event.transition_type == "portfolio_updated":
            self._apply_portfolio_updated(event)
        elif event.transition_type == "risk_updated":
            self._apply_risk_updated(event)
        else:
            raise ValueError(f"Unknown transition_type: {event.transition_type}")

        return self.snapshot(event.portfolio_id, correlation_id=event.correlation_id)

    def _apply_position_opened(self, event: StateTransitionEvent) -> None:
        position = PositionState.model_validate(event.payload["position"])
        cost = float(event.payload["cost"])
        positions = self._portfolio.open_positions + (position,)
        notional = position.entry_price * position.quantity
        exposure_add = notional / self._portfolio.equity * 100 if self._portfolio.equity else 0.0

        self._portfolio = self._portfolio.model_copy(
            update={
                "cash": self._portfolio.cash - cost,
                "open_positions": positions,
                "version": self._portfolio.version + 1,
                "as_of_event_time": event.event_time,
                "as_of_processing_time": event.event_time,
            }
        )
        self._risk = self._risk.model_copy(
            update={
                "open_exposure_pct": self._risk.open_exposure_pct + exposure_add,
                "version": self._risk.version + 1,
                "as_of_event_time": event.event_time,
            }
        )

    def _apply_position_closed(self, event: StateTransitionEvent) -> None:
        position_id = event.payload["position_id"]
        pnl = float(event.payload["pnl"])
        remaining = tuple(p for p in self._portfolio.open_positions if p.position_id != position_id)
        closed = next(
            (p for p in self._portfolio.open_positions if p.position_id == position_id), None
        )
        exposure_drop = 0.0
        if closed:
            notional = closed.entry_price * closed.quantity
            exposure_drop = (
                notional / self._portfolio.equity * 100 if self._portfolio.equity else 0.0
            )

        new_cash = self._portfolio.cash + pnl
        if closed:
            new_cash += closed.entry_price * closed.quantity

        new_equity = self._portfolio.equity + pnl
        consecutive = 0 if pnl >= 0 else self._risk.consecutive_losses + 1

        self._portfolio = self._portfolio.model_copy(
            update={
                "cash": new_cash,
                "equity": new_equity,
                "realized_pnl": self._portfolio.realized_pnl + pnl,
                "open_positions": remaining,
                "version": self._portfolio.version + 1,
                "as_of_event_time": event.event_time,
                "as_of_processing_time": event.event_time,
            }
        )
        self._risk = self._risk.model_copy(
            update={
                "daily_pnl": self._risk.daily_pnl + pnl,
                "open_exposure_pct": max(0.0, self._risk.open_exposure_pct - exposure_drop),
                "consecutive_losses": consecutive,
                "version": self._risk.version + 1,
                "as_of_event_time": event.event_time,
            }
        )

    def _apply_portfolio_updated(self, event: StateTransitionEvent) -> None:
        updates = {k: v for k, v in event.payload.items() if k in PortfolioState.model_fields}
        self._portfolio = self._portfolio.model_copy(
            update={
                **updates,
                "version": self._portfolio.version + 1,
                "as_of_event_time": event.event_time,
            }
        )

    def _apply_risk_updated(self, event: StateTransitionEvent) -> None:
        updates = {k: v for k, v in event.payload.items() if k in RiskState.model_fields}
        self._risk = self._risk.model_copy(
            update={
                **updates,
                "version": self._risk.version + 1,
                "as_of_event_time": event.event_time,
            }
        )

    def _assert_portfolio(self, portfolio_id: str) -> None:
        if portfolio_id != self._portfolio_id:
            raise KeyError(f"Unknown portfolio_id: {portfolio_id}")
