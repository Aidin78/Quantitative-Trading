from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _bb_confidence(
    *,
    close: float,
    upper: float,
    lower: float,
    side: str,
) -> float:
    band_width = max(upper - lower, 1e-9)
    if side == "BUY":
        penetration = max(0.0, (lower - close) / band_width)
    elif side == "SELL":
        penetration = max(0.0, (close - upper) / band_width)
    else:
        return 0.5
    return _clamp(0.55 + 0.4 * penetration, 0.55, 0.95)


class BollingerReversionProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        close = float(features.close)
        upper = float(features.indicators.get("bb_upper", close))
        lower = float(features.indicators.get("bb_lower", close))
        middle = float(features.indicators.get("bb_middle", close))

        min_confidence = float(self.params.get("min_confidence", 0.6))
        avoid_high_vol = bool(self.params.get("avoid_high_vol", True))
        max_adx = float(self.params.get("max_adx", 0.0))

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if close <= lower:
            side = "BUY"
            direction = "bullish"
            summary = f"Price at/below lower Bollinger band ({close:.2f} <= {lower:.2f})"
        elif close >= upper:
            side = "SELL"
            direction = "bearish"
            summary = f"Price at/above upper Bollinger band ({close:.2f} >= {upper:.2f})"
        else:
            side = "HOLD"
            direction = "neutral"
            summary = f"Price inside Bollinger bands ({lower:.2f}–{upper:.2f})"

        confidence = _bb_confidence(close=close, upper=upper, lower=lower, side=side)

        if avoid_high_vol and context.volatility == "HIGH" and side != "HOLD":
            side = "HOLD"
            summary = f"{summary} — high volatility filter"

        if max_adx > 0 and side != "HOLD":
            adx = float(features.indicators.get("adx_14", 0.0))
            if adx > max_adx:
                side = "HOLD"
                summary = f"{summary} — ADX too high for reversion ({adx:.1f} > {max_adx:.1f})"

        rationale = self._rationale(
            summary=summary,
            feature_refs={
                "close": close,
                "bb_upper": upper,
                "bb_lower": lower,
                "bb_middle": middle,
            },
            factors=(
                RationaleFactor(
                    name="bollinger_reversion",
                    weight=1.0,
                    direction=direction,
                    evidence=(
                        f"close={close:.2f}, upper={upper:.2f}, "
                        f"lower={lower:.2f}, middle={middle:.2f}"
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
                        "close": close,
                        "bb_upper": upper,
                        "bb_lower": lower,
                        "bb_middle": middle,
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
