from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _supertrend_confidence(*, close: float, line: float, atr: float) -> float:
    atr_safe = max(atr, 1e-9)
    distance = abs(close - line) / atr_safe
    return _clamp(0.55 + 0.12 * distance, 0.55, 0.95)


class SuperTrendTrendProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        line = float(features.indicators.get("supertrend", context.current_price))
        direction = float(features.indicators.get("supertrend_direction", 0.0))
        close = float(features.close)

        min_confidence = float(self.params.get("min_confidence", 0.6))
        require_trend = bool(self.params.get("require_trend", False))

        side: Literal["BUY", "SELL", "HOLD"]
        trend_direction: Literal["bullish", "bearish", "neutral"]
        if direction > 0:
            side = "BUY"
            trend_direction = "bullish"
            summary = "SuperTrend bullish — price above line"
        elif direction < 0:
            side = "SELL"
            trend_direction = "bearish"
            summary = "SuperTrend bearish — price below line"
        else:
            side = "HOLD"
            trend_direction = "neutral"
            summary = "SuperTrend neutral"

        confidence = _supertrend_confidence(close=close, line=line, atr=context.atr)

        if require_trend:
            if side == "BUY" and context.trend == "DOWN":
                side = "HOLD"
                summary = f"{summary} — trend filter"
            if side == "SELL" and context.trend == "UP":
                side = "HOLD"
                summary = f"{summary} — trend filter"

        rationale = self._rationale(
            summary=summary,
            feature_refs={
                "close": close,
                "supertrend": line,
                "supertrend_direction": direction,
            },
            factors=(
                RationaleFactor(
                    name="supertrend_trend",
                    weight=1.0,
                    direction=trend_direction,
                    evidence=(f"close={close:.2f}, line={line:.2f}, direction={direction:.0f}"),
                ),
            ),
        )

        if side == "HOLD" or confidence < min_confidence:
            hold_summary = summary if side == "HOLD" else f"{summary} — below min confidence"
            return self._build_signal(
                features=features,
                context=context,
                side="HOLD",
                confidence=confidence if side == "HOLD" else min_confidence - 0.01,
                rationale=self._rationale(
                    summary=hold_summary,
                    feature_refs={
                        "close": close,
                        "supertrend": line,
                        "supertrend_direction": direction,
                    },
                    factors=rationale.factors,
                ),
            )

        stop_loss, take_profit = self._atr_stops(context, side)
        return self._build_signal(
            features=features,
            context=context,
            side=side,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rationale=rationale,
        )
