from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.adx_trend_strength import AdxTrendStrengthProvider
from src.providers.base import ProviderConfig
from tests.unit.providers.conftest import make_feature_set


def _adx_features(
    *,
    adx: float = 30.0,
    plus_di: float = 28.0,
    minus_di: float = 15.0,
) -> dict[str, float]:
    return {
        "adx_14": adx,
        "plus_di_14": plus_di,
        "minus_di_14": minus_di,
    }


def test_bullish_trend_emits_buy(context) -> None:
    provider = AdxTrendStrengthProvider(
        ProviderConfig(provider_id="adx_trend_strength", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(indicators=_adx_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.55
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_bearish_trend_emits_sell(context) -> None:
    provider = AdxTrendStrengthProvider(
        ProviderConfig(provider_id="adx_trend_strength", params={"min_confidence": 0.55})
    )
    down_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=context.current_price,
        trend="DOWN",
        volatility=context.volatility,
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(
            indicators=_adx_features(adx=32.0, plus_di=12.0, minus_di=26.0),
        ),
        down_context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.55


def test_weak_adx_emits_hold(context) -> None:
    provider = AdxTrendStrengthProvider(ProviderConfig(provider_id="adx_trend_strength"))
    signal = provider.analyze(
        make_feature_set(indicators=_adx_features(adx=18.0)),
        context,
    )
    assert signal.side == "HOLD"


def test_narrow_di_spread_emits_hold(context) -> None:
    provider = AdxTrendStrengthProvider(
        ProviderConfig(
            provider_id="adx_trend_strength",
            params={"min_di_spread": 10.0},
        )
    )
    signal = provider.analyze(
        make_feature_set(indicators=_adx_features(plus_di=22.0, minus_di=18.0)),
        context,
    )
    assert signal.side == "HOLD"


def test_require_trend_blocks_buy_in_down(context) -> None:
    provider = AdxTrendStrengthProvider(
        ProviderConfig(
            provider_id="adx_trend_strength",
            params={"require_trend": True},
        )
    )
    down_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=context.current_price,
        trend="DOWN",
        volatility=context.volatility,
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(indicators=_adx_features()),
        down_context,
    )
    assert signal.side == "HOLD"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = AdxTrendStrengthProvider(
        ProviderConfig(
            provider_id="adx_trend_strength",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(indicators=_adx_features(adx=26.0, plus_di=22.0, minus_di=18.0)),
        context,
    )
    assert signal.side == "HOLD"
