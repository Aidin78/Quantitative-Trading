from __future__ import annotations

from src.features.config import (
    ContextConfig,
    FeaturesConfig,
    IndicatorDef,
    SessionContextConfig,
    TrendContextConfig,
    VolatilityContextConfig,
    load_features_config,
)
from src.validation.lookback import compute_min_lookback_bars


def test_min_lookback_covers_macd() -> None:
    # macd histogram_slope: slow 26 + signal 9 + 1 => 36, plus 1 buffer => 37
    assert compute_min_lookback_bars() >= 37


def test_min_lookback_covers_adx_two_periods(monkeypatch) -> None:  # noqa: ANN001
    config = FeaturesConfig(
        version="test",
        indicators=(
            IndicatorDef(name="adx_14", type="adx", params={"period": 14, "component": "adx"}),
        ),
        flags=(),
        context=ContextConfig(
            trend=TrendContextConfig(fast="ema_12", slow="ema_26"),
            volatility=VolatilityContextConfig(atr="atr_14", low=0.3, high=1.0),
            session=SessionContextConfig(),
        ),
    )
    monkeypatch.setattr(
        "src.validation.lookback.load_features_config",
        lambda config_dir=None: (config, "hash"),
    )
    # 2 * 14 + 1 buffer
    assert compute_min_lookback_bars() == 29


def test_default_features_lookback_covers_adx_indicator() -> None:
    config, _ = load_features_config()
    adx_periods = [
        int(ind.params.get("period", 14)) for ind in config.indicators if ind.type == "adx"
    ]
    if not adx_periods:
        return
    needed = 2 * max(adx_periods) + 1
    assert compute_min_lookback_bars() >= needed
