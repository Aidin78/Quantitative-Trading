from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _macd_confidence(
    *,
    histogram: float,
    histogram_slope: float,
    atr: float,
) -> float:
    atr_safe = max(atr, 1e-9)
    hist_strength = abs(histogram) / atr_safe
    slope_strength = abs(histogram_slope) / atr_safe
    return _clamp(0.55 + 0.08 * hist_strength + 0.12 * slope_strength, 0.55, 0.95)


class MacdMomentumProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        macd_line = float(features.indicators.get("macd", 0.0))
        macd_signal = float(features.indicators.get("macd_signal", 0.0))
        histogram = float(features.indicators.get("macd_histogram", 0.0))
        histogram_slope = float(features.indicators.get("macd_histogram_slope", 0.0))

        min_confidence = float(self.params.get("min_confidence", 0.6))
        require_signal_align = bool(self.params.get("require_signal_align", True))
        min_histogram_slope = float(self.params.get("min_histogram_slope", 0.0))
        require_trend = bool(self.params.get("require_trend", False))

        bullish = histogram > 0 and histogram_slope > min_histogram_slope
        bearish = histogram < 0 and histogram_slope < -min_histogram_slope

        if require_signal_align:
            bullish = bullish and macd_line > macd_signal
            bearish = bearish and macd_line < macd_signal

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if bullish and not bearish:
            side = "BUY"
            direction = "bullish"
            summary = "MACD histogram momentum bullish"
        elif bearish and not bullish:
            side = "SELL"
            direction = "bearish"
            summary = "MACD histogram momentum bearish"
        else:
            side = "HOLD"
            direction = "neutral"
            summary = "No MACD momentum"

        confidence = _macd_confidence(
            histogram=histogram,
            histogram_slope=histogram_slope,
            atr=context.atr,
        )

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
                "macd": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": histogram,
                "macd_histogram_slope": histogram_slope,
            },
            factors=(
                RationaleFactor(
                    name="macd_momentum",
                    weight=1.0,
                    direction=direction,
                    evidence=(
                        f"histogram={histogram:.6f}, slope={histogram_slope:.6f}, "
                        f"line={macd_line:.6f}, signal={macd_signal:.6f}"
                    ),
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
                        "macd": macd_line,
                        "macd_signal": macd_signal,
                        "macd_histogram": histogram,
                        "macd_histogram_slope": histogram_slope,
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
