from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.contracts.state import StateSnapshot

if TYPE_CHECKING:
    from src.execution.simulated import SimulatedExecutionEngine


def fill_price(
    engine: SimulatedExecutionEngine,
    bar: dict[str, Any],
    side: str,
    *,
    use_next_open: bool = False,
) -> float:
    if use_next_open or engine._fill_model.fill_at == "next_open":
        base = float(bar["open"])
    elif engine._fill_model.fill_at == "mid":
        base = (float(bar["high"]) + float(bar["low"])) / 2
    else:
        base = float(bar["close"])

    slip = engine._fill_model.slippage_bps / 10_000
    if side == "BUY":
        return base * (1 + slip)
    return base * (1 - slip)


def position_size(
    engine: SimulatedExecutionEngine,
    snapshot: StateSnapshot,
    entry: float,
    stop_loss: float,
) -> float:
    portfolio = snapshot.portfolio
    risk = snapshot.risk
    risk_amount = portfolio.equity * engine._config.risk_pct_per_trade / 100
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
