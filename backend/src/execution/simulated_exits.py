from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from src.core.contracts.state import PositionState

if TYPE_CHECKING:
    from src.execution.simulated import SimulatedExecutionEngine


def check_exit(
    engine: SimulatedExecutionEngine,
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

    if check_timeout and bars_held >= engine._config.max_bars_in_trade:
        return "timeout", close

    return None, 0.0
