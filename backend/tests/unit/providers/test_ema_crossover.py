from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.base import ProviderConfig
from src.providers.ema_crossover import EmaCrossoverProvider
from tests.unit.providers.conftest import make_feature_set


def test_bullish_flag_emits_buy(context) -> None:
    provider = EmaCrossoverProvider(
        ProviderConfig(provider_id="ema_crossover", params={"min_confidence": 0.6})
    )
    signal = provider.analyze(
        make_feature_set(
            flags={"ema_cross_bullish": True},
            indicators={"ema_12": 68000.0, "ema_26": 66000.0},
        ),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.6
    assert signal.stop_loss is not None
    assert signal.take_profit is not None
    assert signal.stop_loss < context.current_price
    assert signal.take_profit > context.current_price


def test_no_flag_emits_hold(context) -> None:
    provider = EmaCrossoverProvider(ProviderConfig(provider_id="ema_crossover"))
    signal = provider.analyze(make_feature_set(), context)
    assert signal.side == "HOLD"
    assert signal.confidence == 0.5


def test_below_min_confidence_emits_hold(context) -> None:
    provider = EmaCrossoverProvider(
        ProviderConfig(provider_id="ema_crossover", params={"min_confidence": 0.9})
    )
    signal = provider.analyze(
        make_feature_set(flags={"ema_cross_bullish": True}),
        context,
    )
    assert signal.side == "HOLD"


def test_bearish_flag_emits_sell(context) -> None:
    provider = EmaCrossoverProvider(
        ProviderConfig(
            provider_id="ema_crossover",
            params={"min_confidence": 0.6, "require_trend": False},
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
        make_feature_set(
            flags={"ema_cross_bearish": True},
            indicators={"ema_12": 66000.0, "ema_26": 68000.0},
        ),
        down_context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.6
