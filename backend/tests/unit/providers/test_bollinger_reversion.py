from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.base import ProviderConfig
from src.providers.bollinger_reversion import BollingerReversionProvider
from tests.unit.providers.conftest import make_feature_set


def _bb_features(
    *,
    upper: float = 67200.0,
    lower: float = 66800.0,
    middle: float = 67000.0,
) -> dict[str, float]:
    return {
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_middle": middle,
    }


def test_touch_lower_band_emits_buy(context) -> None:
    provider = BollingerReversionProvider(
        ProviderConfig(provider_id="bollinger_reversion", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(close=66750.0, indicators=_bb_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.55
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_touch_upper_band_emits_sell(context) -> None:
    provider = BollingerReversionProvider(
        ProviderConfig(provider_id="bollinger_reversion", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(close=67250.0, indicators=_bb_features()),
        context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.55


def test_inside_bands_emits_hold(context) -> None:
    provider = BollingerReversionProvider(ProviderConfig(provider_id="bollinger_reversion"))
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_bb_features()),
        context,
    )
    assert signal.side == "HOLD"


def test_high_volatility_filter_emits_hold(context) -> None:
    provider = BollingerReversionProvider(
        ProviderConfig(
            provider_id="bollinger_reversion",
            params={"avoid_high_vol": True},
        )
    )
    high_vol_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=context.current_price,
        trend=context.trend,
        volatility="HIGH",
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(close=66750.0, indicators=_bb_features()),
        high_vol_context,
    )
    assert signal.side == "HOLD"


def test_max_adx_filter_emits_hold(context) -> None:
    provider = BollingerReversionProvider(
        ProviderConfig(
            provider_id="bollinger_reversion",
            params={"max_adx": 25.0},
        )
    )
    indicators = _bb_features()
    indicators["adx_14"] = 30.0
    signal = provider.analyze(
        make_feature_set(close=66750.0, indicators=indicators),
        context,
    )
    assert signal.side == "HOLD"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = BollingerReversionProvider(
        ProviderConfig(
            provider_id="bollinger_reversion",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(close=66800.0, indicators=_bb_features()),
        context,
    )
    assert signal.side == "HOLD"
