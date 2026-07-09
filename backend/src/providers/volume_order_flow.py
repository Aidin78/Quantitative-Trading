from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _volume_flow_confidence(*, cmf: float, volume_ratio: float, min_cmf: float) -> float:
    cmf_strength = min(abs(cmf) / max(min_cmf, 1e-9), 2.0) / 2.0
    vol_strength = min(max(volume_ratio - 1.0, 0.0) / 1.0, 1.0)
    return _clamp(0.55 + 0.2 * cmf_strength + 0.2 * vol_strength, 0.55, 0.95)


class VolumeOrderFlowProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        period = int(self.params.get("period", 20))
        cmf_key = f"cmf_{period}"
        ratio_key = f"volume_ratio_{period}"
        cmf = float(features.indicators.get(cmf_key, features.indicators.get("cmf_20", 0.0)))
        volume_ratio = float(
            features.indicators.get(ratio_key, features.indicators.get("volume_ratio_20", 1.0))
        )
        close_delta = float(features.indicators.get("close_delta", 0.0))

        min_confidence = float(self.params.get("min_confidence", 0.5))
        min_cmf = float(self.params.get("min_cmf", 0.05))
        min_volume_ratio = float(self.params.get("min_volume_ratio", 1.2))
        require_price_align = bool(self.params.get("require_price_align", True))

        volume_confirmed = volume_ratio >= min_volume_ratio
        bullish_flow = cmf >= min_cmf and volume_confirmed
        bearish_flow = cmf <= -min_cmf and volume_confirmed

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if bullish_flow and not bearish_flow:
            side = "BUY"
            direction = "bullish"
            summary = "Volume flow bullish — accumulation with elevated volume"
        elif bearish_flow and not bullish_flow:
            side = "SELL"
            direction = "bearish"
            summary = "Volume flow bearish — distribution with elevated volume"
        else:
            side = "HOLD"
            direction = "neutral"
            if not volume_confirmed:
                summary = "Volume below threshold — weak participation"
            elif abs(cmf) < min_cmf:
                summary = "CMF neutral — no clear money flow"
            else:
                summary = "No volume flow signal"

        if require_price_align and side != "HOLD":
            if side == "BUY" and close_delta <= 0:
                side = "HOLD"
                summary = f"{summary} — price alignment filter"
            elif side == "SELL" and close_delta >= 0:
                side = "HOLD"
                summary = f"{summary} — price alignment filter"

        confidence = _volume_flow_confidence(cmf=cmf, volume_ratio=volume_ratio, min_cmf=min_cmf)

        rationale = self._rationale(
            summary=summary,
            feature_refs={
                cmf_key: cmf,
                ratio_key: volume_ratio,
                "close_delta": close_delta,
            },
            factors=(
                RationaleFactor(
                    name="volume_order_flow",
                    weight=1.0,
                    direction=direction,
                    evidence=(
                        f"cmf={cmf:.4f}, volume_ratio={volume_ratio:.2f}, "
                        f"close_delta={close_delta:.2f}"
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
                        cmf_key: cmf,
                        ratio_key: volume_ratio,
                        "close_delta": close_delta,
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
