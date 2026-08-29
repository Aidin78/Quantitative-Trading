"""Carry runner: one cycle = snapshot -> decide -> plan -> execute -> accrue.

The same loop drives the paper runner (``PaperCarryExecutor`` over historical
snapshots) and, with a live executor + provider, the real thing. Keeping the
loop identical is the point — the paper run is a faithful dry run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from src.carry.perp_provider import PerpSnapshot
from src.carry.position_manager import (
    CarryManagerConfig,
    CarryPositionManager,
    CarryPositionState,
    RebalancePlan,
)


@dataclass(frozen=True)
class ExecReport:
    spot_fill_qty: float
    spot_fill_px: float
    perp_fill_qty: float
    perp_fill_px: float
    fee: float
    reason: str


class CarryExecutor(Protocol):
    def execute(
        self, plan: RebalancePlan, *, spot_px: float, perp_px: float
    ) -> ExecReport | None: ...


@dataclass(frozen=True)
class PaperCarryExecutor:
    """Fills the plan exactly, charging spread+fee on the traded quantity."""

    taker_bps: float = 5.0
    slippage_bps: float = 3.0

    def execute(self, plan: RebalancePlan, *, spot_px: float, perp_px: float) -> ExecReport | None:
        if plan.is_noop:
            return None
        cost_frac = (self.taker_bps + self.slippage_bps) / 10_000.0
        # buy side pays up, sell side receives less
        spot_fill_px = (
            spot_px * (1 + cost_frac) if plan.spot_delta_qty > 0 else spot_px * (1 - cost_frac)
        )
        perp_fill_px = (
            perp_px * (1 - cost_frac) if plan.perp_delta_qty > 0 else perp_px * (1 + cost_frac)
        )
        fee = (abs(plan.spot_delta_qty) * spot_px + abs(plan.perp_delta_qty) * perp_px) * (
            self.taker_bps / 10_000.0
        )
        return ExecReport(
            spot_fill_qty=plan.spot_delta_qty,
            spot_fill_px=spot_fill_px,
            perp_fill_qty=plan.perp_delta_qty,
            perp_fill_px=perp_fill_px,
            fee=fee,
            reason=plan.reason,
        )


@dataclass
class CarryRunLog:
    ts: list[datetime] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


class CarryRunner:
    def __init__(
        self,
        executor: CarryExecutor,
        *,
        initial_capital: float = 10_000.0,
        config: CarryManagerConfig | None = None,
    ) -> None:
        self.manager = CarryPositionManager(config)
        self.executor = executor
        self.cash = initial_capital
        self.state = CarryPositionState()
        self.log = CarryRunLog()

    def equity(self, spot_px: float, perp_px: float) -> float:
        return self.manager.equity(self.state, self.cash, spot_px, perp_px)

    def step(self, snap: PerpSnapshot) -> str:
        target = self.manager.decide_target(
            trailing_funding_8h=snap.trailing_funding_8h,
            equity=self.equity(snap.spot_px, snap.perp_mark_px),
        )
        plan = self.manager.plan(
            self.state, target, spot_px=snap.spot_px, perp_px=snap.perp_mark_px
        )
        action = plan.reason
        report = self.executor.execute(plan, spot_px=snap.spot_px, perp_px=snap.perp_mark_px)
        if report is not None:
            self.state, cash_flow = self.manager.apply_fill(
                self.state,
                spot_fill_qty=report.spot_fill_qty,
                spot_fill_px=report.spot_fill_px,
                perp_fill_qty=report.perp_fill_qty,
                perp_fill_px=report.perp_fill_px,
                fee=report.fee,
            )
            self.cash += cash_flow

        if snap.is_funding_time and self.state.in_market:
            # funding accrues into state.accrued_funding, which equity() adds in
            # (kept separate from cash so it stays visible in the run log)
            self.state = self.manager.accrue_funding(
                self.state, funding_rate=snap.funding_rate, perp_px=snap.perp_mark_px
            )

        self.log.ts.append(snap.ts)
        self.log.equity.append(self.equity(snap.spot_px, snap.perp_mark_px))
        self.log.actions.append(action)
        return action

    def run(self, snapshots) -> CarryRunLog:
        for snap in snapshots:
            self.step(snap)
        return self.log
