"""Combine the basis-carry income leg and the managed long-core growth leg into
one book, with an optional target-volatility overlay.

The carry leg is smooth and low-return; the core leg is lumpy and higher-return.
A weighted blend plus a vol target (scale the book so trailing realised vol
hits a target, leverage capped) is the standard way to dial a return objective
while keeping drawdown bounded. See docs/development/basis-carry-findings.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_ANN = 365


@dataclass(frozen=True)
class BlendConfig:
    carry_weight: float = 0.7
    core_weight: float = 0.3
    target_annual_vol: float | None = 0.13
    vol_window: int = 30
    leverage_cap: float = 3.0


@dataclass
class BlendedBookResult:
    daily_returns: pd.Series
    equity_curve: pd.Series
    monthly_returns: pd.Series
    yearly_returns: pd.Series
    cagr: float
    annual_vol: float
    sharpe: float
    max_drawdown: float
    pct_months_positive: float
    median_month: float
    worst_month: float
    worst_month_date: str | None

    def summary(self) -> dict:
        return {
            "cagr_pct": round(self.cagr * 100, 1),
            "annual_vol_pct": round(self.annual_vol * 100, 1),
            "sharpe": round(self.sharpe, 2),
            "max_drawdown_pct": round(self.max_drawdown * 100, 1),
            "pct_months_positive": round(self.pct_months_positive * 100, 1),
            "median_month_pct": round(self.median_month * 100, 2),
            "worst_month_pct": round(self.worst_month * 100, 2),
            "worst_month_date": self.worst_month_date,
            "n_months": int(len(self.monthly_returns)),
        }


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((1.0 - equity / equity.cummax()).max())


def build_blended_book(
    carry_returns: pd.Series,
    core_returns: pd.Series,
    config: BlendConfig | None = None,
    *,
    core_conviction: pd.Series | None = None,
) -> BlendedBookResult:
    """Blend two daily-return series into one book.

    Inputs are daily simple returns (on deployed capital). They are aligned on
    the union of their dates over the overlapping span; a leg with no value on a
    day contributes 0 that day (e.g. carry flat, or core warming up).

    ``core_conviction`` (optional, values in [0, 1], known at the prior close):
    scales the core sleeve day by day and hands the freed capital to carry —
    so when the trend regime is weak the book leans on the smooth carry leg
    instead of parking idle cash. ``config.core_weight`` is then the *maximum*
    core allocation. Without it the split is static.
    """
    cfg = config or BlendConfig()
    total_w = cfg.carry_weight + cfg.core_weight
    w_carry = cfg.carry_weight / total_w
    w_core = cfg.core_weight / total_w

    carry = carry_returns.copy()
    core = core_returns.copy()
    carry.index = pd.DatetimeIndex(carry.index).tz_localize(None)
    core.index = pd.DatetimeIndex(core.index).tz_localize(None)

    start = max(carry.index.min(), core.index.min())
    end = min(carry.index.max(), core.index.max())
    idx = pd.date_range(start, end, freq="D")
    carry = carry.reindex(idx).fillna(0.0)
    core = core.reindex(idx).fillna(0.0)

    if core_conviction is not None:
        conv = core_conviction.copy()
        conv.index = pd.DatetimeIndex(conv.index).tz_localize(None)
        conv = conv.reindex(idx).ffill().clip(0.0, 1.0).fillna(0.0)
        core_alloc = w_core * conv
        carry_alloc = 1.0 - core_alloc
        raw = carry_alloc * carry + core_alloc * core
    else:
        raw = w_carry * carry + w_core * core

    if cfg.target_annual_vol is not None:
        realised = raw.rolling(cfg.vol_window).std(ddof=1) * np.sqrt(_ANN)
        lev = (cfg.target_annual_vol / realised).clip(upper=cfg.leverage_cap)
        lev = lev.shift(1).fillna(1.0)
        book = raw * lev
    else:
        book = raw

    book = book.rename("blended_book")
    equity = (1.0 + book).cumprod()
    monthly = equity.resample("ME").last().pct_change().dropna()
    yearly = equity.resample("YE").last().pct_change().dropna()

    n_days = len(book)
    cagr = float(equity.iloc[-1] ** (_ANN / n_days) - 1) if n_days else 0.0
    vol = float(book.std(ddof=1) * np.sqrt(_ANN)) if n_days > 1 else 0.0
    sharpe = float(book.mean() / book.std(ddof=1) * np.sqrt(_ANN)) if book.std(ddof=1) > 0 else 0.0
    worst_idx = monthly.idxmin() if not monthly.empty else None

    return BlendedBookResult(
        daily_returns=book,
        equity_curve=equity,
        monthly_returns=monthly,
        yearly_returns=yearly,
        cagr=cagr,
        annual_vol=vol,
        sharpe=sharpe,
        max_drawdown=_max_drawdown(equity),
        pct_months_positive=float((monthly > 0).mean()) if not monthly.empty else 0.0,
        median_month=float(monthly.median()) if not monthly.empty else 0.0,
        worst_month=float(monthly.min()) if not monthly.empty else 0.0,
        worst_month_date=worst_idx.strftime("%Y-%m") if worst_idx is not None else None,
    )
