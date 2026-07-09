from __future__ import annotations

from src.providers.base import ProviderConfig
from src.providers.volume_order_flow import VolumeOrderFlowProvider
from tests.unit.providers.conftest import make_feature_set


def _vol_features(
    *,
    cmf: float = 0.1,
    volume_ratio: float = 1.5,
    close_delta: float = 50.0,
) -> dict[str, float]:
    return {
        "cmf_20": cmf,
        "volume_ratio_20": volume_ratio,
        "close_delta": close_delta,
    }


def test_bullish_flow_emits_buy(context) -> None:
    provider = VolumeOrderFlowProvider(
        ProviderConfig(provider_id="volume_order_flow", params={"min_confidence": 0.5})
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_vol_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.5
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_bearish_flow_emits_sell(context) -> None:
    provider = VolumeOrderFlowProvider(
        ProviderConfig(provider_id="volume_order_flow", params={"min_confidence": 0.5})
    )
    signal = provider.analyze(
        make_feature_set(
            close=66800.0,
            indicators=_vol_features(cmf=-0.1, close_delta=-50.0),
        ),
        context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.5


def test_weak_volume_emits_hold(context) -> None:
    provider = VolumeOrderFlowProvider(ProviderConfig(provider_id="volume_order_flow"))
    signal = provider.analyze(
        make_feature_set(
            close=67000.0,
            indicators=_vol_features(volume_ratio=0.8),
        ),
        context,
    )
    assert signal.side == "HOLD"


def test_weak_cmf_emits_hold(context) -> None:
    provider = VolumeOrderFlowProvider(ProviderConfig(provider_id="volume_order_flow"))
    signal = provider.analyze(
        make_feature_set(
            close=67000.0,
            indicators=_vol_features(cmf=0.01),
        ),
        context,
    )
    assert signal.side == "HOLD"


def test_price_align_blocks_buy_on_falling_close(context) -> None:
    provider = VolumeOrderFlowProvider(
        ProviderConfig(
            provider_id="volume_order_flow",
            params={"require_price_align": True},
        )
    )
    signal = provider.analyze(
        make_feature_set(
            close=67000.0,
            indicators=_vol_features(close_delta=-10.0),
        ),
        context,
    )
    assert signal.side == "HOLD"


def test_price_align_disabled_allows_buy_on_falling_close(context) -> None:
    provider = VolumeOrderFlowProvider(
        ProviderConfig(
            provider_id="volume_order_flow",
            params={"require_price_align": False, "min_confidence": 0.5},
        )
    )
    signal = provider.analyze(
        make_feature_set(
            close=67000.0,
            indicators=_vol_features(close_delta=-10.0),
        ),
        context,
    )
    assert signal.side == "BUY"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = VolumeOrderFlowProvider(
        ProviderConfig(
            provider_id="volume_order_flow",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_vol_features()),
        context,
    )
    assert signal.side == "HOLD"
