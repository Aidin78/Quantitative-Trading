"""Delta-neutral basis-carry backtest.

Position: long ``Q`` spot, short ``Q`` perp of the same notional ``N``. Spot and
perp price moves cancel (delta neutral); the P&L is the funding rate the perp
short collects from perp longs, minus costs.

Modelled explicitly:
  - **capital**: the pair ties up ``N`` in spot plus ``N / perp_leverage`` in
    perp margin; ``capital_multiplier`` (default 1.5) is that ratio with a
    safety buffer. Returns are reported *on deployed capital*.
  - **funding**: sum of the (<=3) 8h funding prints stamped within a day, earned
    on ``N`` when in-market.
  - **flip cost**: opening or closing the pair crosses the spread and pays taker
    fees on both legs — charged once per on/off transition.
  - **rebalance drag**: as spot drifts intraday the hedge ratio drifts; a small
    daily cost keeps it delta-flat.
  - **entry gate**: optionally stay flat while trailing funding is below a
    threshold (default off — always-on carry historically beats gating,
    see docs/development/basis-carry-findings.md).

No basis (spot-perp spread) risk is modelled: the position is assumed held
across settlements where the basis mean-reverts to zero. That is the main
optimism in this backtest and real results run a little worse.

Look-ahead: the in/out decision for day ``D`` uses only funding prints stamped
strictly before ``D`` 00:00 UTC; the funding earned on day ``D`` is that day's
own prints.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_ANN = 365
_PRINTS_PER_DAY = 3


@dataclass(frozen=True)
class BasisCarryConfig:
    capital_multiplier: float = 1.5
    flip_cost: float = 0.0006
    rebalance_drag_daily: float = 3.0e-5
    min_trailing_funding_8h: float = -1.0  # default: always-on
    trail_prints: int = 3


@dataclass
class BasisCarryResult:
    daily_returns: pd.Series
    gross_funding_annual: float
    net_annual: float
    days_in_market: int
    n_flips: int
    pct_days_in_market: float


def simulate_basis_carry(
    funding: pd.DataFrame,
    config: BasisCarryConfig | None = None,
) -> BasisCarryResult:
    """Backtest the carry on a funding-rate frame (``timestamp``, ``funding_rate``).

    ``daily_returns`` is on deployed capital, indexed by calendar day (UTC).
    """
    cfg = config or BasisCarryConfig()
    if funding.empty:
        return BasisCarryResult(pd.Series(dtype=float), 0.0, 0.0, 0, 0, 0.0)

    f = funding.sort_values("timestamp").copy()
    f["day"] = f["timestamp"].dt.floor("D")
    daily_gross = f.groupby("day")["funding_rate"].sum()
    daily_gross.index = pd.DatetimeIndex(daily_gross.index)

    trailing_mean = (
        f.set_index("timestamp")["funding_rate"]
        .rolling(f"{cfg.trail_prints * 8}h")
        .mean()
        .resample("D")
        .last()
        .shift(1)
    )
    hold = trailing_mean.reindex(daily_gross.index).ge(cfg.min_trailing_funding_8h).fillna(False)

    flips = hold.astype(int).diff().abs().fillna(hold.astype(int))
    gross = daily_gross.where(hold, 0.0)
    costs = flips * cfg.flip_cost + hold.astype(float) * cfg.rebalance_drag_daily
    daily_returns = ((gross - costs) / cfg.capital_multiplier).rename("basis_carry")

    in_market = int(hold.sum())
    return BasisCarryResult(
        daily_returns=daily_returns,
        gross_funding_annual=float(daily_gross.mean() * _ANN),
        net_annual=float(daily_returns.mean() * _ANN),
        days_in_market=in_market,
        n_flips=int(flips.sum()),
        pct_days_in_market=in_market / len(hold) if len(hold) else 0.0,
    )
