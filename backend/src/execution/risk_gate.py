from __future__ import annotations

from dataclasses import dataclass

from src.core.contracts.execution import OrderIntent
from src.core.contracts.state import StateSnapshot


@dataclass(frozen=True)
class ExecutionRiskResult:
    passed: bool
    reason: str | None = None


class ExecutionRiskGate:
    def check(self, intent: OrderIntent, snapshot: StateSnapshot) -> ExecutionRiskResult:
        portfolio = snapshot.portfolio
        risk = snapshot.risk
        limits = risk.limits

        if len(portfolio.open_positions) >= limits.max_open_positions:
            return ExecutionRiskResult(False, "max_open_positions")

        notional = intent.quantity * (intent.limit_price or 0.0)
        if intent.limit_price is None:
            return ExecutionRiskResult(False, "missing_entry_price")

        exposure_pct = (
            (risk.open_exposure_pct * portfolio.equity / 100 + notional) / portfolio.equity * 100
        )
        if exposure_pct > limits.max_exposure_pct:
            return ExecutionRiskResult(False, "max_exposure")

        cost = notional
        if cost > portfolio.cash:
            return ExecutionRiskResult(False, "insufficient_cash")

        return ExecutionRiskResult(True)
