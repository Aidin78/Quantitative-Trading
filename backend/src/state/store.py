from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, Protocol

from src.core.contracts.state import PortfolioState, RiskLimits, RiskState, StateSnapshot
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
        raise NotImplementedError("State transitions are implemented in Phase 4 execution layer")

    def _assert_portfolio(self, portfolio_id: str) -> None:
        if portfolio_id != self._portfolio_id:
            raise KeyError(f"Unknown portfolio_id: {portfolio_id}")
