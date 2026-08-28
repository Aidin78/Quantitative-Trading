#!/usr/bin/env python3
"""Phase-1-style screen for a NEW hypothesis class: perpetual funding rate.

Every classic-TA lead (EMA/MACD/RSI/ADX/BB/ST/MS, ensembles, order-flow,
higher timeframes, the ADX-1d sweep) has now been rejected on real
fill/fee — see docs/development/edge-investigation-findings.md and
provider-edge-htf-experiment-plan.md §10. Those all read price trajectory.
Funding rate is a different information source: it is the periodic payment
between perp longs and shorts, i.e. a direct read on *leverage/positioning*,
not price direction. Economic prior: persistently high positive funding =
crowded, over-leveraged longs = elevated squeeze risk (contrarian short);
persistently negative funding = crowded shorts (contrarian long).

This script is statistical-only, same contract as run_signal_research.py:
no Decision Engine, no provider instantiation, no execution. It screens the
funding signal for raw predictive power BEFORE any provider/feature is built.
A pass here is necessary, not sufficient — it would still have to survive
provider_edge_scorecard under real sizing/fills.

Look-ahead rule (load-bearing): a daily spot bar t is timestamped at day
00:00 UTC and closes at day+1 00:00. Funding is stamped at 00:00 / 08:00 /
16:00 UTC, so all of day t's funding events are known by day t's close.
``fund_day_t`` (their sum) is therefore a backward-looking signal at t, and
is compared only against ``fwd_ret_h`` (= close[t+h]/close[t]-1) from
signal_evaluator.compute_forward_targets. Nothing here reads a future bar.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.data.market_cache import resolve_cache_dir  # noqa: E402
from src.research.classification_phase import (  # noqa: E402
    _directional_win_rate,
    _net_of_fees,
    _trade_pnls,
)
from src.research.signal_evaluator import compute_forward_targets, load_ohlcv  # noqa: E402

HORIZONS: tuple[int, ...] = (1, 3, 7, 14, 30)
PERCENTILES: tuple[float, ...] = (80.0, 90.0, 95.0)
RANK_WINDOW = 180  # trailing days for the funding percentile rank
TRAIL_SUM_DAYS = 3  # trailing funding sum the signal keys off


# --------------------------------------------------------------------------- #
# Funding-rate download + cache (ccxt; market_cache only handles OHLCV)
# --------------------------------------------------------------------------- #
def _funding_cache_path(symbol: str) -> Path:
    safe = symbol.replace("/", "-")
    return resolve_cache_dir() / f"binance_funding_{safe}_8h.csv"


def _perp_symbol(spot_symbol: str) -> str:
    base, quote = spot_symbol.split("/")
    return f"{base}/{quote}:{quote}"


def _download_funding(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Full funding-rate history for the perp of ``symbol`` (8h cadence), cached to CSV."""
    import ccxt

    path = _funding_cache_path(symbol)
    if path.exists():
        cached = pd.read_csv(path)
        cached["timestamp"] = pd.to_datetime(cached["timestamp"], utc=True, format="ISO8601")
        covered = (
            not cached.empty
            and cached["timestamp"].iloc[0] <= pd.Timestamp(start)
            and cached["timestamp"].iloc[-1] >= pd.Timestamp(end) - pd.Timedelta(days=2)
        )
        if covered:
            return cached

    exchange = ccxt.binance({"options": {"defaultType": "future"}, "timeout": 20000})
    perp = _perp_symbol(symbol)
    since = exchange.parse8601(start.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end_ms = exchange.parse8601(end.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rows: list[dict] = []
    while since < end_ms:
        batch = exchange.fetch_funding_rate_history(perp, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1]["timestamp"] + 1
        if len(batch) < 1000:
            break
    frame = (
        pd.DataFrame(
            {
                "timestamp": pd.to_datetime([r["timestamp"] for r in rows], unit="ms", utc=True),
                "funding_rate": [float(r["fundingRate"]) for r in rows],
            }
        )
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


# --------------------------------------------------------------------------- #
# Feature construction (all backward-looking at bar t)
# --------------------------------------------------------------------------- #
def _attach_funding_features(df: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    """Add per-day funding columns to a daily OHLCV frame (``timestamp`` column)."""
    out = df.copy()
    ts = pd.to_datetime(out["timestamp"], utc=True)
    day = ts.dt.floor("D")

    fund = funding.copy()
    fund["day"] = fund["timestamp"].dt.floor("D")
    # Percent per day: sum of the (<=3) 8h funding prints stamped within the day.
    daily = fund.groupby("day")["funding_rate"].sum().mul(100.0)
    out["fund_day"] = day.map(daily).astype(float).fillna(0.0).to_numpy()

    out["fund_trail"] = out["fund_day"].rolling(TRAIL_SUM_DAYS, min_periods=1).sum()

    def _rank_of_last(window: np.ndarray) -> float:
        if window.size < 2:
            return 50.0
        return float((window[:-1] < window[-1]).mean() * 100.0)

    out["fund_rank"] = (
        out["fund_trail"].rolling(RANK_WINDOW, min_periods=30).apply(_rank_of_last, raw=True)
    )
    return out


def _framing_signals(row_rank: pd.Series, row_trail: pd.Series, pct: float) -> dict[str, pd.Series]:
    """Return {framing_name: UP/DOWN/'' Series} for one percentile threshold."""
    hi = row_rank >= pct
    lo = row_rank <= (100.0 - pct)
    contrarian = pd.Series("", index=row_rank.index, dtype=object)
    contrarian[hi] = "DOWN"  # crowded longs -> fade
    contrarian[lo] = "UP"
    momentum = pd.Series("", index=row_rank.index, dtype=object)
    momentum[hi] = "UP"
    momentum[lo] = "DOWN"
    sign_contra = pd.Series("", index=row_trail.index, dtype=object)
    sign_contra[row_trail > 0] = "DOWN"
    sign_contra[row_trail < 0] = "UP"
    return {
        "contrarian_rank": contrarian,
        "momentum_rank": momentum,
        "sign_contrarian": sign_contra,
    }


# --------------------------------------------------------------------------- #
# Screen
# --------------------------------------------------------------------------- #
#: A directional signal in a trending asset earns ``E[side] * E[fwd_ret]`` for
#: free — that is drift captured by net long/short exposure, not predictive
#: skill. The real edge is expectancy *in excess* of that null. This must be
#: positive after fees, on BOTH the full (overlapping) sample and a
#: non-overlapping subsample (signals spaced >= horizon apart), by at least:
PASS_EXCESS_NET_PCT = 0.10


def _nonoverlap_mask(active: pd.Series, horizon: int) -> pd.Series:
    """Keep active bars spaced at least ``horizon`` apart (independent samples)."""
    keep = pd.Series(False, index=active.index)
    last = -(10**9)
    active_positions = np.flatnonzero(active.to_numpy())
    for pos in active_positions:
        if pos - last >= horizon:
            keep.iloc[pos] = True
            last = pos
    return keep


def _signed_expectancy(df: pd.DataFrame, signal: pd.Series, horizon: int, mask=None):
    """(net expectancy %, n, mean side in {-1..1}) for the active (masked) bars."""
    fwd = df[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna()
    if mask is not None:
        active = active & mask
    pnls = _trade_pnls(df, signal, horizon=horizon, mask=mask)
    net = _net_of_fees(pnls)
    sides = np.where(signal[active] == "UP", 1.0, -1.0)
    mean_side = float(sides.mean()) if sides.size else 0.0
    return net, int(active.sum()), mean_side


def _screen_row(df: pd.DataFrame, signal: pd.Series, horizon: int, base_mean_fwd: float) -> dict:
    net, n, mean_side = _signed_expectancy(df, signal, horizon)
    _, win_rate = _directional_win_rate(df, signal, horizon=horizon)
    null_exp = mean_side * base_mean_fwd  # drift earned by net exposure alone
    excess_net = net.expectancy - null_exp if net.trades else float("nan")

    fwd = df[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna()
    no_mask = _nonoverlap_mask(active, horizon)
    net_no, n_no, mean_side_no = _signed_expectancy(df, signal, horizon, mask=no_mask)
    excess_net_no = (
        net_no.expectancy - mean_side_no * base_mean_fwd if net_no.trades else float("nan")
    )

    subwins = _subwindow_net_expectancy(df, signal, horizon)
    sub_pos = sum(
        1 for w in subwins if w["net_expectancy_pct"] is not None and w["net_expectancy_pct"] > 0
    )

    passes = (
        n_no >= 30
        and np.isfinite(excess_net)
        and np.isfinite(excess_net_no)
        and excess_net > PASS_EXCESS_NET_PCT
        and excess_net_no > PASS_EXCESS_NET_PCT
        # raw (not just drift-adjusted) net expectancy must hold up out of sample:
        and net.expectancy > 0
        and sub_pos >= 2
    )
    return {
        "horizon": horizon,
        "trades": n,
        "trades_nonoverlap": n_no,
        "win_rate": round(win_rate, 2) if not np.isnan(win_rate) else None,
        "mean_side": round(mean_side, 3),
        "net_expectancy_pct": round(net.expectancy, 4) if net.trades else None,
        "null_drift_expectancy_pct": round(null_exp, 4),
        "excess_net_pct": round(excess_net, 4) if np.isfinite(excess_net) else None,
        "excess_net_nonoverlap_pct": (
            round(excess_net_no, 4) if np.isfinite(excess_net_no) else None
        ),
        "subwindows": subwins,
        "subwindows_net_positive": f"{sub_pos}/3",
        "passes": bool(passes),
    }


def _subwindow_net_expectancy(
    df: pd.DataFrame, signal: pd.Series, horizon: int, n: int = 3
) -> list:
    bounds = np.linspace(0, len(df), n + 1, dtype=int)
    out = []
    for i in range(n):
        lo, hi = bounds[i], bounds[i + 1]
        mask = pd.Series(False, index=df.index)
        mask.iloc[lo:hi] = True
        pnls = _trade_pnls(df, signal, horizon=horizon, mask=mask)
        net = _net_of_fees(pnls)
        out.append(
            {
                "window": f"{i + 1}/{n}",
                "trades": net.trades,
                "net_expectancy_pct": round(net.expectancy, 4) if net.trades else None,
            }
        )
    return out


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Funding-rate signal screen (statistical only)")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--start", default="2019-09-10")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--out", default=str(_BACKEND / "data" / "funding_signal_research.json"))
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    payload: dict = {
        "start": args.start,
        "end": args.end,
        "timeframe": args.timeframe,
        "rank_window_days": RANK_WINDOW,
        "trail_sum_days": TRAIL_SUM_DAYS,
        "round_trip_cost_note": (
            "net = gross - 2*(fee_bps+slippage_bps)/100 via load_default_fill_model"
        ),
        "symbols": {},
    }

    any_pass = False
    for symbol in [s.strip() for s in args.symbols.split(",")]:
        print(f"\n===== {symbol} {args.timeframe} =====", flush=True)
        df = await load_ohlcv(
            source="exchange",
            symbol=symbol,
            timeframe=args.timeframe,
            start=start,
            end=end,
        )
        funding = _download_funding(symbol, start, end)
        print(
            f"  {len(df)} spot bars | {len(funding)} funding prints "
            f"({funding['timestamp'].iloc[0].date()} -> {funding['timestamp'].iloc[-1].date()})",
            flush=True,
        )
        df = compute_forward_targets(df, horizons=HORIZONS)
        df = _attach_funding_features(df, funding)

        base_mean_fwd = {h: float(df[f"fwd_ret_{h}"].dropna().mean()) for h in HORIZONS}
        print(
            "  unconditional mean fwd_ret (drift null): "
            + " ".join(f"h{h}={base_mean_fwd[h]:+.2f}%" for h in HORIZONS),
            flush=True,
        )

        sym_rows: list[dict] = []
        for pct in PERCENTILES:
            framings = _framing_signals(df["fund_rank"], df["fund_trail"], pct)
            for fname, signal in framings.items():
                for h in HORIZONS:
                    row = _screen_row(df, signal, h, base_mean_fwd[h])
                    row["framing"] = fname
                    row["threshold_pct"] = pct
                    if row["passes"]:
                        any_pass = True
                    sym_rows.append(row)

        # sign_contrarian is threshold-free; keep only its pct==80 copy.
        sym_rows = [
            r
            for r in sym_rows
            if not (r["framing"] == "sign_contrarian" and r["threshold_pct"] != 80.0)
        ]

        best = sorted(
            (r for r in sym_rows if r["excess_net_nonoverlap_pct"] is not None),
            key=lambda r: r["excess_net_nonoverlap_pct"],
            reverse=True,
        )[:5]
        print("  top-5 by drift-adjusted excess (non-overlapping):", flush=True)
        for r in best:
            print(
                f"    {r['framing']:<16} p{r['threshold_pct']:.0f} h={r['horizon']:<2} "
                f"n={r['trades']:<4} n_no={r['trades_nonoverlap']:<3} win%={r['win_rate']} "
                f"net={r['net_expectancy_pct']} null={r['null_drift_expectancy_pct']} "
                f"excess={r['excess_net_pct']} excess_no={r['excess_net_nonoverlap_pct']} "
                f"{'** PASS **' if r['passes'] else ''}",
                flush=True,
            )
        n_pass = sum(1 for r in sym_rows if r["passes"])
        print(f"  PASS rows: {n_pass}/{len(sym_rows)}", flush=True)
        passing_framings = sorted({r["framing"] for r in sym_rows if r["passes"]})
        payload["symbols"][symbol] = {
            "rows": sym_rows,
            "pass_count": n_pass,
            "passing_framings": passing_framings,
        }

    # Cross-symbol consistency: a real funding-structure edge must point the
    # same way on BTC and ETH (same mechanism, ~0.9 correlated). Different
    # winning framings per symbol = two independent overfits, not one edge.
    framing_sets = [set(v["passing_framings"]) for v in payload["symbols"].values()]
    shared = set.intersection(*framing_sets) if framing_sets else set()
    payload["shared_passing_framings"] = sorted(shared)
    payload["any_pass"] = any_pass

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    if not any_pass:
        verdict = "NO edge — every framing failed the screen"
    elif not shared:
        verdict = (
            "REJECT — framings that pass differ per symbol "
            f"({ {s: v['passing_framings'] for s, v in payload['symbols'].items()} }); "
            "no single hypothesis survives across symbols"
        )
    else:
        verdict = (
            f"shared framing(s) pass across all symbols: {sorted(shared)} "
            "— worth a real scorecard"
        )
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
