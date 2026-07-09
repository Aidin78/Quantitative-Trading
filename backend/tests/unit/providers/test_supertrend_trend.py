from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.base import ProviderConfig
from src.providers.supertrend_trend import SuperTrendTrendProvider
from tests.unit.providers.conftest import make_feature_set


def _st_features(
    *,
    line: float = 66800.0,
    direction: float = 1.0,
) -> dict[str, float]:
    return {
        "supertrend": line,
        "supertrend_direction": direction,
    }


def test_bullish_direction_emits_buy(context) -> None:
    provider = SuperTrendTrendProvider(
        ProviderConfig(provider_id="supertrend_trend", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_st_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.55
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_bearish_direction_emits_sell(context) -> None:
    provider = SuperTrendTrendProvider(
        ProviderConfig(provider_id="supertrend_trend", params={"min_confidence": 0.55})
    )
    down_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=66800.0,
        trend="DOWN",
        volatility=context.volatility,
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(
            close=66800.0,
            indicators=_st_features(line=67200.0, direction=-1.0),
        ),
        down_context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.55


def test_neutral_direction_emits_hold(context) -> None:
    provider = SuperTrendTrendProvider(ProviderConfig(provider_id="supertrend_trend"))
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_st_features(direction=0.0)),
        context,
    )
    assert signal.side == "HOLD"


def test_require_trend_blocks_buy_in_down(context) -> None:
    provider = SuperTrendTrendProvider(
        ProviderConfig(
            provider_id="supertrend_trend",
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
        make_feature_set(close=67000.0, indicators=_st_features()),
        down_context,
    )
    assert signal.side == "HOLD"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = SuperTrendTrendProvider(
        ProviderConfig(
            provider_id="supertrend_trend",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(
            close=66810.0,
            indicators=_st_features(line=66800.0, direction=1.0),
        ),
        context,
    )
    assert signal.side == "HOLD"
