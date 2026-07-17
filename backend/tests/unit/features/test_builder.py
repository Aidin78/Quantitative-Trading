from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.features.builder import DefaultFeatureBuilder
from src.features.config import (
    FeaturesConfig,
    IndicatorDef,
    load_features_config,
)
from src.features.indicators.base import register_indicator
from src.features.store import InMemoryFeatureStore
from tests.fixtures.ohlcv import make_sample_ohlcv

SNAPSHOT_PROCESSING_TIME = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)


def test_builder_snapshot_stable_output(
    ohlcv_df: pd.DataFrame,
    fixed_processing_time: datetime,
) -> None:
    builder = DefaultFeatureBuilder()
    fs1, ctx1 = builder.build(
        ohlcv_df,
        "BTC/USDT",
        "1h",
        processing_time=fixed_processing_time,
        persist=False,
    )
    fs2, ctx2 = builder.build(
        ohlcv_df,
        "BTC/USDT",
        "1h",
        processing_time=fixed_processing_time,
        persist=False,
    )

    assert fs1.indicators == fs2.indicators
    assert fs1.flags == fs2.flags
    assert ctx1 == ctx2
    assert fs1.feature_version == "v1"
    assert len(fs1.config_hash) == 64
    assert fs1.close == pytest.approx(float(ohlcv_df["close"].iloc[-1]), rel=1e-6)
    assert "rsi_14" in fs1.indicators
    assert "ema_12" in fs1.indicators
    assert "macd" in fs1.indicators
    assert "macd_signal" in fs1.indicators
    assert "macd_histogram" in fs1.indicators
    assert "macd_histogram_slope" in fs1.indicators
    assert "macd_bullish" in fs1.flags
    assert "ema_cross_bullish" in fs1.flags


def test_market_context_derived_from_builder_not_manual(
    ohlcv_df: pd.DataFrame,
    fixed_processing_time: datetime,
) -> None:
    builder = DefaultFeatureBuilder()
    fs, ctx = builder.build(
        ohlcv_df,
        "BTC/USDT",
        "1h",
        processing_time=fixed_processing_time,
        persist=False,
    )

    if fs.indicators["ema_12"] > fs.indicators["ema_26"]:
        assert ctx.trend == "UP"
        assert fs.flags["ema_cross_bullish"] is True
    elif fs.indicators["ema_12"] < fs.indicators["ema_26"]:
        assert ctx.trend == "DOWN"
        assert fs.flags["ema_cross_bullish"] is False
    else:
        assert ctx.trend == "SIDEWAYS"

    assert ctx.atr == pytest.approx(fs.indicators["atr_14"])
    expected_atr_pct = fs.indicators["atr_14"] / fs.close * 100
    assert ctx.atr_pct == pytest.approx(expected_atr_pct, rel=1e-3, abs=1e-3)
    assert ctx.current_price == fs.close
    assert ctx.event_time.tzinfo is not None


def test_builder_persists_to_store(ohlcv_df: pd.DataFrame, fixed_processing_time: datetime) -> None:
    store = InMemoryFeatureStore()
    builder = DefaultFeatureBuilder(store=store)
    fs, ctx = builder.build(
        ohlcv_df,
        "BTC/USDT",
        "1h",
        processing_time=fixed_processing_time,
    )
    record = store.get(fs.feature_set_id)
    assert record.market_context == ctx
    assert store.get_at("BTC/USDT", "1h", fs.event_time, fs.feature_version) is not None


def test_rsi_computed_once_per_build(
    monkeypatch: pytest.MonkeyPatch, ohlcv_df: pd.DataFrame
) -> None:
    builder = DefaultFeatureBuilder()
    calls: list[str] = []
    original = builder._registry.compute_indicator

    def tracked(definition, df, **kwargs):  # noqa: ANN001
        if definition.name == "rsi_14":
            calls.append(definition.name)
        return original(definition, df, **kwargs)

    monkeypatch.setattr(builder._registry, "compute_indicator", tracked)
    builder.build(ohlcv_df, "BTC/USDT", "1h", persist=False)
    assert calls.count("rsi_14") == 1


def test_extensibility_new_indicator_type(ohlcv_df: pd.DataFrame) -> None:
    @register_indicator("constant")
    class ConstantIndicator:
        def compute(self, df: pd.DataFrame, params: dict) -> float:  # noqa: ANN001
            return float(params.get("value", 1.0))

    base_config, config_hash = load_features_config()
    extra = IndicatorDef(name="test_const", type="constant", params={"value": 42.0})
    extended = FeaturesConfig(
        version=base_config.version,
        indicators=base_config.indicators + (extra,),
        flags=base_config.flags,
        context=base_config.context,
    )
    builder = DefaultFeatureBuilder(config=extended, config_hash=config_hash)
    fs, _ = builder.build(ohlcv_df, "BTC/USDT", "1h", persist=False)
    assert fs.indicators["test_const"] == 42.0


def test_features_module_has_no_engine_or_provider_imports() -> None:
    features_root = Path(__file__).resolve().parents[2] / "src" / "features"
    forbidden = ("src.engine", "src.providers", "from engine", "from providers")
    for path in features_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in content, f"{path} contains forbidden import: {token}"


def test_write_ohlcv_fixture_csv() -> None:
    csv_path = Path(__file__).resolve().parents[2] / "fixtures" / "ohlcv_btc_1h.csv"
    if not csv_path.exists():
        df = make_sample_ohlcv()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
    assert csv_path.exists()
