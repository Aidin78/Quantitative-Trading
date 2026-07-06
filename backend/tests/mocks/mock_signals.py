from __future__ import annotations

from datetime import datetime
from typing import Literal

from src.core.contracts.rationale import ProviderRationale
from src.core.contracts.signal import StrategySignal


def make_signal(
    provider_id: str,
    side: Literal["BUY", "SELL", "HOLD"],
    confidence: float = 0.75,
    *,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    event_time: datetime,
    weight: float = 1.0,
    stop_loss: float | None = 66500.0,
    take_profit: float | None = 68500.0,
    summary: str | None = None,
) -> StrategySignal:
    rationale = ProviderRationale(
        summary=summary or f"{provider_id} {side}",
        metadata={"weight": weight},
    )
    return StrategySignal(
        provider_id=provider_id,
        symbol=symbol,
        side=side,
        confidence=confidence,
        rationale=rationale,
        feature_set_id="fs_test_001",
        entry_price=67000.0,
        stop_loss=stop_loss if side == "BUY" else 67500.0,
        take_profit=take_profit if side == "BUY" else 65500.0,
        timeframe=timeframe,
        event_time=event_time,
    )


def consensus_buy_signals(event_time: datetime) -> list[StrategySignal]:
    return [
        make_signal("ema_crossover", "BUY", 0.78, event_time=event_time),
        make_signal("rsi_divergence", "BUY", 0.72, event_time=event_time),
    ]


def conflict_signals(event_time: datetime) -> list[StrategySignal]:
    return [
        make_signal("ema_crossover", "BUY", 0.78, event_time=event_time),
        make_signal("rsi_divergence", "SELL", 0.72, event_time=event_time),
    ]
