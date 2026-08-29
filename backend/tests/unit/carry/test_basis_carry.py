from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.carry.basis_carry import BasisCarryConfig, simulate_basis_carry


def _funding(rate_per_8h: float, days: int, start: str = "2023-01-01") -> pd.DataFrame:
    ts = pd.date_range(start, periods=days * 3, freq="8h", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "funding_rate": np.full(len(ts), rate_per_8h)})


def test_empty_funding_returns_zeroed_result() -> None:
    r = simulate_basis_carry(pd.DataFrame({"timestamp": [], "funding_rate": []}))
    assert r.daily_returns.empty
    assert r.net_annual == 0.0


def test_positive_funding_earns_carry_net_of_capital_haircut() -> None:
    # 1 bp / 8h = 3 bp/day = ~10.95%/yr gross on notional
    r = simulate_basis_carry(_funding(0.0001, 400), BasisCarryConfig(rebalance_drag_daily=0.0))
    gross = 0.0001 * 3 * 365
    assert r.gross_funding_annual == pytest.approx(gross, rel=1e-6)
    # net is on deployed capital (1.5x), minus one entry flip
    assert r.net_annual == pytest.approx(gross / 1.5, rel=0.05)
    assert r.net_annual < r.gross_funding_annual


def test_negative_funding_loses_when_always_on() -> None:
    r = simulate_basis_carry(_funding(-0.00005, 300))
    assert r.net_annual < 0
    # always-on: in market every day except day 1 (no trailing data to decide on)
    assert r.pct_days_in_market > 0.99


def test_entry_gate_sits_out_negative_funding() -> None:
    # first 150 days negative funding, then positive
    neg = _funding(-0.00008, 150, start="2023-01-01")
    pos = _funding(0.00012, 150, start="2023-05-31")
    funding = pd.concat([neg, pos], ignore_index=True)
    gated = simulate_basis_carry(
        funding, BasisCarryConfig(min_trailing_funding_8h=0.0, rebalance_drag_daily=0.0)
    )
    always = simulate_basis_carry(funding, BasisCarryConfig(rebalance_drag_daily=0.0))
    assert gated.pct_days_in_market < always.pct_days_in_market
    assert gated.net_annual > always.net_annual  # skipped the negative stretch


def test_flip_cost_charged_on_each_transition() -> None:
    funding = _funding(0.0001, 100)
    cheap = simulate_basis_carry(funding, BasisCarryConfig(flip_cost=0.0, rebalance_drag_daily=0.0))
    pricey = simulate_basis_carry(
        funding, BasisCarryConfig(flip_cost=0.01, rebalance_drag_daily=0.0)
    )
    # one entry flip => pricey is worse by ~ flip_cost / capital_multiplier
    assert cheap.daily_returns.sum() - pricey.daily_returns.sum() == pytest.approx(
        0.01 / 1.5, rel=1e-6
    )
