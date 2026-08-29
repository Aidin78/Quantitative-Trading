#!/usr/bin/env python3
"""Does a BTC+ETH *portfolio* of managed long-core legs beat a single-asset
managed core and a 50/50 buy-and-hold — statistically, before any porting?

The single-asset managed core (docs/development/managed-long-core-findings.md)
halves buy&hold drawdown but gives up raw return. BTC and ETH are ~0.8
correlated, not 1.0, so a 50/50 book of the two managed legs should shave
drawdown further (diversification) and may recover some of the return/risk
tradeoff. This checks that before building a multi-asset runtime.

Legs: per asset, w_i[t] = gate_i[t] * clip(target / vol_i[t], 0, cap), applied
to r_i[t+1]. Portfolio = 0.5 * (leg_btc + leg_eth), turnover-costed on |dw|.

Benchmarks: 50/50 BTC+ETH buy&hold (the fair one), BTC buy&hold, and each
single-asset managed leg. Also a vol-matched view: scale each series to the
50/50 buy&hold's realized vol and compare return + drawdown at equal risk.

Look-ahead: gate/vol at t use data <= t; weight applied to r[t+1].
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

from src.execution.config import load_default_fill_model  # noqa: E402
from src.research.signal_evaluator import load_ohlcv  # noqa: E402

ANN = 365
SMA_N = 150
VOL_W = 30
TARGET_ANN_VOL = 0.5
CAP = 1.5


def _perf(daily_returns: np.ndarray) -> dict:
    r = daily_returns[np.isfinite(daily_returns)]
    if r.size < 60:
        return dict.fromkeys(("ann_return", "ann_vol", "sharpe", "max_dd", "calmar"))
    mean, std = float(r.mean()), float(r.std(ddof=1))
    ann_return = mean * ANN
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    max_dd = float((1.0 - equity / peak).max())
    return {
        "ann_return": round(ann_return, 4),
        "ann_vol": round(std * (ANN**0.5), 4),
        "sharpe": round(mean / std * (ANN**0.5), 3) if std > 0 else 0.0,
        "max_dd": round(max_dd, 4),
        "calmar": round(ann_return / max_dd, 3) if max_dd > 0 else None,
    }


def _regime_gate(close: pd.Series, sma_n: int) -> pd.Series:
    return (close > close.rolling(sma_n).mean()).fillna(False).astype(float)


def _leg_weights(close: pd.Series, ret: pd.Series) -> pd.Series:
    gate = _regime_gate(close, SMA_N)
    pred_daily_vol = ret.rolling(VOL_W).std(ddof=1)
    size = (TARGET_ANN_VOL / (ANN**0.5) / pred_daily_vol).clip(lower=0.0, upper=CAP)
    return (gate * size).shift(1)


def _vol_match(series: np.ndarray, target_vol_series: np.ndarray) -> np.ndarray:
    """Scale `series` so its realized daily std equals target's, then report."""
    s = series[np.isfinite(series) & np.isfinite(target_vol_series)]
    t = target_vol_series[np.isfinite(series) & np.isfinite(target_vol_series)]
    if s.std(ddof=1) <= 0:
        return series
    return series * (t.std(ddof=1) / s.std(ddof=1))


def _subwindows(series: dict[str, np.ndarray], n: int = 3) -> list[dict]:
    length = len(next(iter(series.values())))
    bounds = np.linspace(0, length, n + 1, dtype=int)
    out = []
    for i in range(n):
        row = {"window": f"{i + 1}/{n}"}
        for name, arr in series.items():
            p = _perf(arr[bounds[i] : bounds[i + 1]])
            row[name] = {
                "calmar": p["calmar"],
                "max_dd": p["max_dd"],
                "ann_return": p["ann_return"],
            }
        out.append(row)
    return out


async def _legs(symbol: str, start: datetime, end: datetime, cost: float):
    df = await load_ohlcv(source="exchange", symbol=symbol, timeframe="1d", start=start, end=end)
    df = df.copy()
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True)
    close = df.set_index("ts")["close"]
    ret = close.pct_change()
    w = _leg_weights(close, ret)
    gross = w * ret
    turn = w.diff().abs().fillna(w.abs())
    net = gross - turn * cost
    return pd.DataFrame({"bh": ret, "managed": net})


async def _run() -> int:
    parser = argparse.ArgumentParser(description="BTC+ETH managed-core portfolio screen")
    parser.add_argument("--start", default="2017-08-17")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument(
        "--out", default=str(_BACKEND / "data" / "core_long_portfolio_research.json")
    )
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    fm = load_default_fill_model()
    cost = (fm.fee_bps + fm.slippage_bps) / 10_000.0

    btc = await _legs("BTC/USDT", start, end, cost)
    eth = await _legs("ETH/USDT", start, end, cost)
    joined = btc.join(eth, lsuffix="_btc", rsuffix="_eth", how="inner").dropna(
        subset=["bh_btc", "bh_eth"]
    )

    series = {
        "btc_buyhold": joined["bh_btc"].to_numpy(),
        "eth_buyhold": joined["bh_eth"].to_numpy(),
        "5050_buyhold": (0.5 * (joined["bh_btc"] + joined["bh_eth"])).to_numpy(),
        "btc_managed": joined["managed_btc"].to_numpy(),
        "eth_managed": joined["managed_eth"].to_numpy(),
        "portfolio_managed": (
            0.5 * (joined["managed_btc"].fillna(0) + joined["managed_eth"].fillna(0))
        ).to_numpy(),
    }

    def _report(label: str, subset: dict[str, np.ndarray]) -> dict:
        print(f"\n===== {label} =====", flush=True)
        bench = subset["5050_buyhold"]
        table = {}
        for name, arr in subset.items():
            p = _perf(arr)
            vm = _perf(_vol_match(arr, bench))
            table[name] = {"raw": p, "vol_matched": vm}
            print(
                f"  {name:<18} ret={p['ann_return']} vol={p['ann_vol']} sharpe={p['sharpe']} "
                f"maxDD={p['max_dd']} calmar={p['calmar']}  |  @5050-vol: "
                f"ret={vm['ann_return']} maxDD={vm['max_dd']} calmar={vm['calmar']}",
                flush=True,
            )
        return table

    payload: dict = {
        "params": {"sma_n": SMA_N, "vol_w": VOL_W, "target_ann_vol": TARGET_ANN_VOL, "cap": CAP},
        "one_way_cost": cost,
        "n_days": int(len(joined)),
        "full_history": _report("full history", series),
    }

    cut = joined.index.searchsorted(pd.Timestamp("2022-01-01", tz="UTC"))
    sub_2022 = {k: v[cut:] for k, v in series.items()}
    payload["from_2022"] = _report("from 2022-01", sub_2022)
    payload["subwindows"] = _subwindows(series)

    pm = _perf(series["portfolio_managed"])
    bh = _perf(series["5050_buyhold"])
    btc_m = _perf(series["btc_managed"])
    eth_m = _perf(series["eth_managed"])
    improves_dd = pm["max_dd"] < min(btc_m["max_dd"], eth_m["max_dd"])
    beats_bh_calmar = pm["calmar"] is not None and pm["calmar"] >= bh["calmar"] * 1.30

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    print("\nVERDICT:", flush=True)
    print(
        f"  portfolio maxDD {pm['max_dd']} vs best single-leg managed "
        f"{min(btc_m['max_dd'], eth_m['max_dd'])} -> "
        f"{'diversifies' if improves_dd else 'no diversification benefit'}",
        flush=True,
    )
    print(
        f"  portfolio Calmar {pm['calmar']} vs 50/50 buy&hold {bh['calmar']} -> "
        f"{'PASS (>=1.3x)' if beats_bh_calmar else 'below 1.3x bar'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
