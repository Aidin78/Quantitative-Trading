from __future__ import annotations

import numpy as np
import pandas as pd

from src.carry.blended_book import BlendConfig, build_blended_book


def _series(mean: float, vol: float, n: int, seed: int, start: str = "2022-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, vol, n), index=idx)


def test_weights_are_normalised() -> None:
    carry = _series(0.0003, 0.001, 600, 1)
    core = _series(0.0008, 0.03, 600, 2)
    a = build_blended_book(
        carry, core, BlendConfig(carry_weight=7, core_weight=3, target_annual_vol=None)
    )
    b = build_blended_book(
        carry, core, BlendConfig(carry_weight=0.7, core_weight=0.3, target_annual_vol=None)
    )
    pd.testing.assert_series_equal(a.daily_returns, b.daily_returns)


def test_vol_target_brings_realised_vol_near_target() -> None:
    carry = _series(0.0003, 0.0008, 900, 1)
    core = _series(0.0005, 0.04, 900, 2)
    res = build_blended_book(carry, core, BlendConfig(target_annual_vol=0.15, leverage_cap=10.0))
    # realised annual vol should land in a reasonable band around the target
    assert 0.10 < res.annual_vol < 0.22


def test_carry_heavy_book_is_smoother_than_core_heavy() -> None:
    carry = _series(0.00035, 0.0008, 900, 1)
    core = _series(0.0009, 0.04, 900, 2)
    carry_heavy = build_blended_book(
        carry, core, BlendConfig(carry_weight=0.9, core_weight=0.1, target_annual_vol=None)
    )
    core_heavy = build_blended_book(
        carry, core, BlendConfig(carry_weight=0.3, core_weight=0.7, target_annual_vol=None)
    )
    assert carry_heavy.max_drawdown < core_heavy.max_drawdown
    assert carry_heavy.pct_months_positive >= core_heavy.pct_months_positive


def test_summary_shape() -> None:
    carry = _series(0.0003, 0.001, 400, 1)
    core = _series(0.001, 0.03, 400, 2)
    s = build_blended_book(carry, core).summary()
    for key in ("cagr_pct", "sharpe", "max_drawdown_pct", "pct_months_positive", "worst_month_pct"):
        assert key in s
    assert s["n_months"] >= 10


def test_overlapping_span_only() -> None:
    carry = _series(0.0003, 0.001, 500, 1, start="2021-01-01")
    core = _series(0.001, 0.03, 500, 2, start="2021-06-01")
    res = build_blended_book(carry, core, BlendConfig(target_annual_vol=None))
    assert res.daily_returns.index.min() >= pd.Timestamp("2021-06-01")
