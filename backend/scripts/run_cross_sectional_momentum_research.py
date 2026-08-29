#!/usr/bin/env python3
"""Screen cross-sectional (relative-strength) momentum across a coin basket.

Context: every SINGLE-ASSET timing hypothesis has been rejected — classic TA
(1h/4h/1d), ensembles, order-flow, the ADX-1d sweep, funding rate, and
volatility-regime sizing (see docs/development/*-findings.md and
provider-edge-htf-experiment-plan.md §10). This is a structurally different
mechanism: instead of predicting whether ONE asset goes up, rank a basket by
trailing return and go long the strongest / short the weakest, rebalancing
periodically. Crypto cross-sectional momentum is one of the few crypto
premia with external academic support (Liu, Tsyvinski & Wu 2022).

Statistical-only, same contract as the other research scripts: no engine, no
provider, no execution. A pass here still has to survive a real long/short
backtest with borrow/short constraints before anything is built.

Rigor (learned from the funding & vol-targeting screens):
  - baseline is the EQUAL-WEIGHT basket ("the crypto market"), not zero and
    not 50%; a long/short book is also compared against zero (market-neutral)
  - metric is Sharpe + max drawdown, net of rebalance turnover cost from
    load_default_fill_model
  - must hold in >=2/3 chronological subwindows
  - survivorship caveat: the universe is CURRENTLY-listed Binance coins, so
    delisted losers are missing — this biases results OPTIMISTICALLY. A clean
    reject here is strong; a pass must be re-checked on a survivorship-free set.

Look-ahead: the signal at rebalance date t uses prices up to t-skip only; the
resulting weights earn the return from t to the next rebalance. No future bar.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.data.market_cache import get_or_download_csv  # noqa: E402
from src.execution.config import load_default_fill_model  # noqa: E402

ANN = 365

# Binance-listed coins with daily history starting no later than 2020-Q1 (the
# 2020+ DeFi batch enters the panel when its data begins). Currently-listed
# only -> survivorship bias, documented above.
UNIVERSE: tuple[str, ...] = (
    "BTC",
    "ETH",
    "BNB",
    "XRP",
    "LTC",
    "ADA",
    "BCH",
    "LINK",
    "XLM",
    "TRX",
    "ETC",
    "EOS",
    "NEO",
    "DASH",
    "XMR",
    "ZEC",
    "ATOM",
    "DOGE",
    "VET",
    "WAVES",
    "ONT",
    "QTUM",
    "ICX",
    "ZIL",
    "BAT",
    "IOTA",
    "ALGO",
    "MATIC",
    "THETA",
    "XTZ",
    "ENJ",
    "CHZ",
    "SOL",
    "AVAX",
    "DOT",
    "UNI",
    "AAVE",
    "SUSHI",
    "YFI",
    "COMP",
    "SNX",
    "MKR",
    "FIL",
    "EGLD",
    "MANA",
    "SAND",
    "GRT",
    "CRV",
)

LOOKBACKS: tuple[int, ...] = (7, 14, 30, 60, 90)
REBALANCE_DAYS: tuple[int, ...] = (7, 14, 30)
TOP_N: tuple[int, ...] = (3, 5, 8)
SKIP_DAYS = 1  # standard 1-bar skip to sidestep very-short-term reversal
PASS_SHARPE_MARGIN = 0.3  # long/short book must clear this absolute Sharpe AND beat basket


async def _load_close_panel(
    symbols: tuple[str, ...], start: datetime, end: datetime
) -> pd.DataFrame:
    """(dates x coins) close-price panel; a coin is NaN before its listing."""
    series: dict[str, pd.Series] = {}
    for coin in symbols:
        sym = f"{coin}/USDT"
        try:
            path = await get_or_download_csv(
                exchange_id="binance", symbol=sym, timeframe="1d", start=start, end=end
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {coin}: {type(exc).__name__} {exc}", flush=True)
            continue
        raw = pd.read_csv(path)
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
        s = raw.set_index("timestamp")["close"].sort_index()
        s = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
        series[coin] = s
    panel = pd.DataFrame(series).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    return panel


def _perf(daily_returns: np.ndarray) -> dict:
    r = daily_returns[np.isfinite(daily_returns)]
    if r.size < 30:
        return {k: None for k in ("ann_return", "ann_vol", "sharpe", "max_dd")}
    mean, std = float(r.mean()), float(r.std(ddof=1))
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    return {
        "ann_return": round(mean * ANN, 4),
        "ann_vol": round(std * (ANN**0.5), 4),
        "sharpe": round(mean / std * (ANN**0.5), 3) if std > 0 else 0.0,
        "max_dd": round(float((1.0 - equity / peak).max()), 4),
    }


def _subwindow_sharpes(returns: np.ndarray, n: int = 3) -> list[float | None]:
    bounds = np.linspace(0, len(returns), n + 1, dtype=int)
    return [_perf(returns[bounds[i] : bounds[i + 1]])["sharpe"] for i in range(n)]


def _backtest(
    panel: pd.DataFrame,
    prices_ret: pd.DataFrame,
    *,
    lookback: int,
    rebalance: int,
    top_n: int,
    cost: float,
) -> dict:
    dates = panel.index
    rebal_idx = list(range(lookback + SKIP_DAYS + 1, len(dates) - 1, rebalance))
    ls_daily: list[float] = []  # long/short (dollar-neutral) daily returns
    lo_daily: list[float] = []  # long-only top-N daily returns
    bench_daily: list[float] = []  # equal-weight all-available daily returns
    prev_long: set[str] = set()
    prev_short: set[str] = set()

    for k, ri in enumerate(rebal_idx):
        past = panel.iloc[ri - SKIP_DAYS]
        base = panel.iloc[ri - SKIP_DAYS - lookback]
        mom = (past / base - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
        # require a live (non-NaN) price at the formation date too
        mom = mom[panel.iloc[ri].reindex(mom.index).notna()]
        if len(mom) < 2 * top_n + 2:
            continue
        ranked = mom.sort_values()
        shorts = set(ranked.index[:top_n])
        longs = set(ranked.index[-top_n:])

        end_i = rebal_idx[k + 1] if k + 1 < len(rebal_idx) else len(dates) - 1
        hold = prices_ret.iloc[ri + 1 : end_i + 1]

        long_leg = hold[list(longs)].mean(axis=1)
        short_leg = hold[list(shorts)].mean(axis=1)
        avail = [c for c in mom.index]
        bench_leg = hold[avail].mean(axis=1)

        turn_ls = (len(longs ^ prev_long) + len(shorts ^ prev_short)) / max(2 * top_n, 1)
        turn_lo = len(longs ^ prev_long) / max(top_n, 1)
        ls = (long_leg - short_leg).to_numpy()
        lo = long_leg.to_numpy()
        bn = bench_leg.to_numpy()
        if ls.size:
            ls[0] -= turn_ls * cost * 2  # both legs turn
            lo[0] -= turn_lo * cost
        ls_daily.extend(ls.tolist())
        lo_daily.extend(lo.tolist())
        bench_daily.extend(bn.tolist())
        prev_long, prev_short = longs, shorts

    ls_arr = np.array(ls_daily)
    lo_arr = np.array(lo_daily)
    bn_arr = np.array(bench_daily)
    ls_perf = _perf(ls_arr)
    lo_perf = _perf(lo_arr)
    bn_perf = _perf(bn_arr)
    ls_subs = _subwindow_sharpes(ls_arr)
    lo_subs = _subwindow_sharpes(lo_arr)
    lo_bench_subs = _subwindow_sharpes(bn_arr)

    ls_beats = sum(1 for s in ls_subs if s is not None and s >= PASS_SHARPE_MARGIN)
    lo_beats = sum(
        1
        for s, b in zip(lo_subs, lo_bench_subs, strict=False)
        if s is not None and b is not None and s - b >= PASS_SHARPE_MARGIN
    )
    ls_pass = (
        ls_perf["sharpe"] is not None and ls_perf["sharpe"] >= PASS_SHARPE_MARGIN and ls_beats >= 2
    )
    lo_pass = (
        lo_perf["sharpe"] is not None
        and bn_perf["sharpe"] is not None
        and lo_perf["sharpe"] - bn_perf["sharpe"] >= PASS_SHARPE_MARGIN
        and lo_beats >= 2
    )
    return {
        "lookback": lookback,
        "rebalance": rebalance,
        "top_n": top_n,
        "rebalances": len(rebal_idx),
        "long_short": {**ls_perf, "subwindow_sharpe": ls_subs, "passes": bool(ls_pass)},
        "long_only_top": {**lo_perf, "subwindow_sharpe": lo_subs, "passes": bool(lo_pass)},
        "equal_weight_basket": {**bn_perf, "subwindow_sharpe": lo_bench_subs},
    }


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Cross-sectional momentum screen (statistical)")
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument(
        "--out", default=str(_BACKEND / "data" / "cross_sectional_momentum_research.json")
    )
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    cost = (load_default_fill_model().fee_bps + load_default_fill_model().slippage_bps) / 10_000.0

    print(f"Loading {len(UNIVERSE)} coins {args.start}->{args.end} ...", flush=True)
    panel = await _load_close_panel(UNIVERSE, start, end)
    prices_ret = panel.pct_change()
    coverage = panel.notna().sum(axis=1)
    mid = len(coverage) // 2
    print(
        f"  panel {panel.shape[0]} days x {panel.shape[1]} coins | coins available: "
        f"start={int(coverage.iloc[0])} mid={int(coverage.iloc[mid])} end={int(coverage.iloc[-1])}",
        flush=True,
    )

    btc = prices_ret["BTC"].to_numpy() if "BTC" in prices_ret else np.array([])
    print(f"  BTC buy&hold: {_perf(btc)}", flush=True)

    rows: list[dict] = []
    for lb, rb, tn in itertools.product(LOOKBACKS, REBALANCE_DAYS, TOP_N):
        res = _backtest(panel, prices_ret, lookback=lb, rebalance=rb, top_n=tn, cost=cost)
        rows.append(res)
        ls, lo, bn = res["long_short"], res["long_only_top"], res["equal_weight_basket"]
        print(
            f"  L={lb:<2} R={rb:<2} N={tn} | "
            f"L/S sharpe={ls['sharpe']} dd={ls['max_dd']} {'PASS' if ls['passes'] else ''}  |  "
            f"long-only sharpe={lo['sharpe']} vs basket {bn['sharpe']} "
            f"{'PASS' if lo['passes'] else ''}",
            flush=True,
        )

    ls_pass = [r for r in rows if r["long_short"]["passes"]]
    lo_pass = [r for r in rows if r["long_only_top"]["passes"]]
    payload = {
        "start": args.start,
        "end": args.end,
        "universe": list(UNIVERSE),
        "skip_days": SKIP_DAYS,
        "one_way_cost": cost,
        "pass_sharpe_margin": PASS_SHARPE_MARGIN,
        "survivorship_caveat": "currently-listed Binance coins only; biases results optimistically",
        "btc_buyhold": _perf(btc),
        "rows": rows,
        "long_short_pass_count": len(ls_pass),
        "long_only_pass_count": len(lo_pass),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    if ls_pass:
        verdict = (
            f"long/short cross-sectional momentum PASSES in {len(ls_pass)} config(s) "
            "(Sharpe >= 0.3, market-neutral, >=2/3 subwindows) — take to a real L/S backtest "
            "with borrow constraints and a survivorship-free universe"
        )
    elif lo_pass:
        verdict = (
            f"long-only top-N beats the equal-weight basket in {len(lo_pass)} config(s) "
            "— weaker result (still long-biased); check survivorship sensitivity"
        )
    else:
        verdict = (
            "REJECT — neither the market-neutral long/short book nor long-only top-N "
            "beats its baseline robustly, even with survivorship bias helping"
        )
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
