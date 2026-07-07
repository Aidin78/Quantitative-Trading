from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import MarketEventType, build_envelope
from src.features.drift import compare_features
from src.replay.feature_rebuild import rebuild_indicators


@pytest.fixture
def csv_fixture_path() -> Path:
    root = Path(__file__).resolve().parents[1] / "fixtures"
    for name in ("sample_btc_1h.csv", "ohlcv_btc_1h.csv"):
        path = root / name
        if path.exists():
            return path
    pytest.skip("OHLCV fixture missing")


def test_rebuild_indicators_matches_stored(csv_fixture_path: Path) -> None:
    import pandas as pd

    from src.features.builder import DefaultFeatureBuilder

    df = pd.read_csv(csv_fixture_path, parse_dates=["timestamp"])
    builder = DefaultFeatureBuilder()
    feature_set, _ = builder.build(df.tail(200), "BTC/USDT", "1h", persist=False)
    event_time = feature_set.event_time

    feature_event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.FEATURE_SET_BUILT,
        event_time=event_time,
        processing_time=datetime.now(UTC),
        correlation_id="drift_test",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "feature_set_id": feature_set.feature_set_id,
            "feature_version": feature_set.feature_version,
            "config_hash": feature_set.config_hash,
            "indicators": feature_set.indicators,
            "flags": feature_set.flags,
        },
    )

    rebuilt = rebuild_indicators(feature_event, csv_path=str(csv_fixture_path))
    assert rebuilt is not None
    drift = compare_features(feature_set.indicators, rebuilt)
    assert drift["detected"] is False
    assert drift["drift_count"] == 0


def test_compare_features_detects_numeric_delta() -> None:
    drift = compare_features({"rsi": 50.0}, {"rsi": 55.0})
    assert drift["detected"] is True
    assert drift["drift_count"] == 1
