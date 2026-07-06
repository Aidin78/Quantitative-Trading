from __future__ import annotations

from src.core.contracts.signal import StrategySignal
from src.engine.config import AggregationConfig
from src.engine.models import AggregatorFailure, AggregatorOutcome, AggregatorSuccess


def _provider_weight(signal: StrategySignal) -> float:
    weight = signal.rationale.metadata.get("weight", 1.0)
    return float(weight)


class Aggregator:
    def __init__(self, config: AggregationConfig) -> None:
        self._config = config

    def combine(self, signals: list[StrategySignal]) -> AggregatorOutcome:
        method = self._config.method
        if method == "unanimous":
            return self._combine_unanimous(signals)
        weighted = method == "weighted_majority"
        return self._combine_majority(signals, weighted=weighted)

    def _combine_unanimous(self, signals: list[StrategySignal]) -> AggregatorOutcome:
        active = [s for s in signals if s.side != "HOLD"]
        if not active:
            return AggregatorFailure(reason="no_active_signals")

        sides = {s.side for s in active}
        if len(sides) != 1:
            return AggregatorFailure(reason="provider_conflict")

        side = active[0].side
        if side not in ("BUY", "SELL"):
            return AggregatorFailure(reason="insufficient_consensus")

        if len(active) < self._config.min_agreeing_providers:
            return AggregatorFailure(reason="insufficient_consensus")

        return self._success(active, [], side, weighted=True)

    def _combine_majority(
        self, signals: list[StrategySignal], *, weighted: bool
    ) -> AggregatorOutcome:
        active = [s for s in signals if s.side != "HOLD"]
        if not active:
            return AggregatorFailure(reason="no_active_signals")

        buys = [s for s in active if s.side == "BUY"]
        sells = [s for s in active if s.side == "SELL"]
        min_agree = self._config.min_agreeing_providers

        if len(buys) >= min_agree and len(buys) > len(sells):
            return self._success(buys, sells, "BUY", weighted=weighted)
        if len(sells) >= min_agree and len(sells) > len(buys):
            return self._success(sells, buys, "SELL", weighted=weighted)

        if buys and sells:
            return AggregatorFailure(reason="provider_conflict")

        return AggregatorFailure(reason="insufficient_consensus")

    def _success(
        self,
        winners: list[StrategySignal],
        losers: list[StrategySignal],
        side: str,
        *,
        weighted: bool,
    ) -> AggregatorSuccess:
        weights: dict[str, float] = {}
        if weighted:
            weighted_sum = 0.0
            weight_total = 0.0
            for signal in winners:
                w = _provider_weight(signal)
                weights[signal.provider_id] = w
                weighted_sum += signal.confidence * w
                weight_total += w
            confidence = weighted_sum / weight_total if weight_total else 0.0
        else:
            for signal in winners:
                weights[signal.provider_id] = 1.0
            confidence = sum(s.confidence for s in winners) / len(winners)

        dissent = tuple(s.provider_id for s in losers)
        return AggregatorSuccess(
            side=side,  # type: ignore[arg-type]
            confidence=confidence,
            weights=weights,
            dissent=dissent,
        )
