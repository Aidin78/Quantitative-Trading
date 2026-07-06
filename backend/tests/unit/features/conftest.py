from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.features.builder import DefaultFeatureBuilder
from src.features.config import load_features_config
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    csv_path = Path(__file__).resolve().parents[1] / "fixtures" / "ohlcv_btc_1h.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path, parse_dates=["timestamp"])
    return make_sample_ohlcv()


@pytest.fixture
def feature_builder() -> DefaultFeatureBuilder:
    return DefaultFeatureBuilder()


@pytest.fixture
def fixed_processing_time() -> datetime:
    return datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def features_config():
    config, config_hash = load_features_config()
    return config, config_hash
