from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.config import resolve_config_dir
from src.providers import load_providers


@pytest.fixture
def csv_path() -> Path:
    for name in ("sample_btc_1h.csv", "ohlcv_btc_1h.csv"):
        path = Path(__file__).resolve().parents[1] / "fixtures" / name
        if path.exists():
            return path
    pytest.skip("CSV fixture missing")


@pytest.fixture
def real_providers():
    return load_providers(resolve_config_dir())
