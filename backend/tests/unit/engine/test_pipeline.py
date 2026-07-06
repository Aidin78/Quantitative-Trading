import pytest

from src.engine.aggregator import Aggregator
from src.engine.config import AggregationConfig, FilterConfig
from src.engine.market_filter import MarketFilter
from tests.mocks.fixtures import make_context, utc_now
from tests.mocks.mock_signals import conflict_signals, consensus_buy_signals, make_signal


def test_market_filter_rejects_low_atr() -> None:
    filt = MarketFilter(FilterConfig(min_atr_pct=0.5, allowed_sessions=("EUROPE",)))
    result = filt.check(make_context(atr_pct=0.2))
    assert not result.passed
    assert result.reason == "atr_below_minimum"


def test_aggregator_insufficient_single_provider() -> None:
    agg = Aggregator(AggregationConfig(min_agreeing_providers=2, method="weighted_majority"))
    signals = consensus_buy_signals(utc_now())[:1]
    outcome = agg.combine(signals)
    assert hasattr(outcome, "reason")
    assert outcome.reason == "insufficient_consensus"  # type: ignore[union-attr]


def test_aggregator_conflict() -> None:
    agg = Aggregator(AggregationConfig(min_agreeing_providers=1, method="weighted_majority"))
    outcome = agg.combine(conflict_signals(utc_now()))
    assert hasattr(outcome, "reason")
    assert outcome.reason == "provider_conflict"  # type: ignore[union-attr]


def test_aggregator_unanimous_requires_same_side() -> None:
    agg = Aggregator(AggregationConfig(min_agreeing_providers=2, method="unanimous"))
    outcome = agg.combine(consensus_buy_signals(utc_now()))
    assert hasattr(outcome, "side")
    assert outcome.side == "BUY"  # type: ignore[union-attr]

    conflict = agg.combine(conflict_signals(utc_now()))
    assert hasattr(conflict, "reason")
    assert conflict.reason == "provider_conflict"  # type: ignore[union-attr]


def test_aggregator_majority_simple_average() -> None:
    agg = Aggregator(AggregationConfig(min_agreeing_providers=2, method="majority"))
    now = utc_now()
    signals = [
        *consensus_buy_signals(now),
        make_signal("macd_momentum", "SELL", 0.9, event_time=now),
    ]
    outcome = agg.combine(signals)
    assert hasattr(outcome, "side")
    assert outcome.side == "BUY"  # type: ignore[union-attr]
    assert outcome.confidence == pytest.approx(0.75)  # type: ignore[union-attr]
