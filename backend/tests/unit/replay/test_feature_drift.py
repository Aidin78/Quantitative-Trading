from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import MarketEventType, build_envelope
from src.features.config import load_features_config
from src.features.drift import compare_features
from src.governance.revision_store import compute_config_revision
from src.replay.feature_rebuild import rebuild_indicators
from src.replay.reexecutor import _detect_feature_drift


@pytest.fixture
def csv_fixture_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "fixtures"
    for name in ("sample_btc_1h.csv", "ohlcv_btc_1h.csv"):
        path = root / name
        if path.exists():
            return path
    pytest.skip("OHLCV fixture missing")


def test_features_config_hash_matches_revision() -> None:
    _, features_hash = load_features_config()
    revision = compute_config_revision()
    assert features_hash == revision.features_config_hash
    assert len(features_hash) == 64


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
    drift = compare_features(
        feature_set.indicators,
        rebuilt["indicators"],
        stored_flags=feature_set.flags,
        rebuilt_flags=rebuilt["flags"],
    )
    assert drift["detected"] is False
    assert drift["drift_count"] == 0


def test_compare_features_detects_numeric_delta() -> None:
    drift = compare_features({"rsi": 50.0}, {"rsi": 55.0})
    assert drift["detected"] is True
    assert drift["drift_count"] == 1


def test_compare_features_detects_flag_delta() -> None:
    drift = compare_features(
        {"rsi": 50.0},
        {"rsi": 50.0},
        stored_flags={"trend_up": True},
        rebuilt_flags={"trend_up": False},
    )
    assert drift["detected"] is True
    assert drift["drift_count"] == 1
    assert drift["drifts"][0]["key"] == "trend_up"


def test_detect_feature_drift_no_drift(csv_fixture_path: Path) -> None:
    import pandas as pd

    from src.features.builder import DefaultFeatureBuilder

    df = pd.read_csv(csv_fixture_path, parse_dates=["timestamp"])
    builder = DefaultFeatureBuilder()
    feature_set, _ = builder.build(df.tail(200), "BTC/USDT", "1h", persist=False)
    feature_event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.FEATURE_SET_BUILT,
        event_time=feature_set.event_time,
        processing_time=datetime.now(UTC),
        correlation_id="drift_ok",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "config_hash": feature_set.config_hash,
            "indicators": feature_set.indicators,
            "flags": feature_set.flags,
        },
    )
    report = _detect_feature_drift(feature_event, csv_path=str(csv_fixture_path))
    assert report["detected"] is False
    assert report.get("rebuild_skipped") is not True


def test_detect_feature_drift_config_hash_mismatch(csv_fixture_path: Path) -> None:
    import pandas as pd

    from src.features.builder import DefaultFeatureBuilder

    df = pd.read_csv(csv_fixture_path, parse_dates=["timestamp"])
    builder = DefaultFeatureBuilder()
    feature_set, _ = builder.build(df.tail(200), "BTC/USDT", "1h", persist=False)
    feature_event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.FEATURE_SET_BUILT,
        event_time=feature_set.event_time,
        processing_time=datetime.now(UTC),
        correlation_id="drift_hash",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "config_hash": "0" * 64,
            "indicators": feature_set.indicators,
            "flags": feature_set.flags,
        },
    )
    report = _detect_feature_drift(feature_event, csv_path=str(csv_fixture_path))
    assert report["detected"] is True
    assert report["reason"] == "config_hash_mismatch"
    assert report["config_hash_stored"] == "0" * 64
    assert report["config_hash_current"] == feature_set.config_hash


def test_detect_feature_drift_rebuild_skipped_when_csv_missing() -> None:
    now = datetime.now(UTC)
    feature_event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.FEATURE_SET_BUILT,
        event_time=now,
        processing_time=now,
        correlation_id="drift_skip",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "config_hash": "",
            "indicators": {"rsi": 50.0},
            "flags": {},
        },
    )
    report = _detect_feature_drift(
        feature_event,
        csv_path="/nonexistent/path/missing_ohlcv.csv",
    )
    assert report["rebuild_skipped"] is True
    assert report["reason"] == "ohlcv_unavailable"
