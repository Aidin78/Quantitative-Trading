from __future__ import annotations

from src.providers.base import ProviderConfig
from src.providers.core_long import CoreLongProvider
from tests.unit.providers.conftest import make_feature_set


def _provider(**params) -> CoreLongProvider:
    return CoreLongProvider(ProviderConfig(provider_id="core_long", params=params))


def test_buy_when_price_above_sma(context) -> None:
    signal = _provider().analyze(
        make_feature_set(indicators={"sma_200": 50000.0}),  # context price 67000
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence == 0.9
    assert signal.stop_loss is not None and signal.stop_loss < context.current_price
    assert signal.take_profit is not None and signal.take_profit > context.current_price


def test_hold_when_price_below_sma(context) -> None:
    signal = _provider().analyze(
        make_feature_set(indicators={"sma_200": 80000.0}),
        context,
    )
    assert signal.side == "HOLD"
    assert signal.confidence == 0.5


def test_regime_off_side_sell_opt_in(context) -> None:
    signal = _provider(regime_off_side="SELL").analyze(
        make_feature_set(indicators={"sma_200": 80000.0}),
        context,
    )
    assert signal.side == "SELL"
    assert signal.stop_loss is not None and signal.stop_loss > context.current_price


def test_hold_when_sma_missing(context) -> None:
    signal = _provider().analyze(make_feature_set(indicators={}), context)
    assert signal.side == "HOLD"
    assert "not available" in signal.rationale.summary


def test_no_stops_when_atr_stops_disabled(context) -> None:
    signal = _provider(use_atr_stops=False).analyze(
        make_feature_set(indicators={"sma_200": 50000.0}),
        context,
    )
    assert signal.side == "BUY"
    assert signal.stop_loss is None
    assert signal.take_profit is None


def test_below_min_confidence_holds(context) -> None:
    signal = _provider(confidence=0.5, min_confidence=0.6).analyze(
        make_feature_set(indicators={"sma_200": 50000.0}),
        context,
    )
    assert signal.side == "HOLD"
