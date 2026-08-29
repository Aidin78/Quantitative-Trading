#!/usr/bin/env python3
"""Option 1 screen: is a risk-managed long crypto core a better *vehicle* than
naked buy-and-hold?

This is NOT an alpha search — every one of those was rejected (see
docs/development/*-findings.md). The question here is narrower and honest:
given that holding crypto beta has a positive long-run drift but ~80-95%
drawdowns, does layering (a) a trend-based risk-off switch and (b)
volatility-targeted sizing produce a materially better *risk-adjusted*
vehicle — higher Calmar, much lower max drawdown — while keeping most of the
return, robustly across subwindows and both BTC and ETH?

The overlay is expected to give up some absolute return (it sits out part of
every rally). The bar is: Calmar (ann_return / max_dd) clearly beats
buy-and-hold, max drawdown is cut by a wide margin, and both hold in >=2/3
chronological subwindows on BOTH symbols. If that holds, port to a real
CoreLongProvider + a RiskManager sizing policy + a regime gate and validate
through ValidationHarness.

Components
  - regime gate: in-market when close > SMA(N), optionally requiring the
    condition to persist `confirm` days (whipsaw guard). Trend as a risk-off
    switch, not a direction predictor (Moskowitz-Ooi-Pedersen tail-hedge).
  - vol targeting: w = target_ann_vol / realized_vol(W), clipped [0, cap].
  - combined: w[t] = in_market[t] * clip(target/vol[t], 0, cap).

Look-ahead: gate and vol at bar t use only closes/returns up to t; the weight
is applied to r[t+1]. Turnover cost from load_default_fill_model on |dw|.
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

from src.execution.config import load_default_fill_model  # noqa: E402
from src.research.signal_evaluator import load_ohlcv  # noqa: E402

ANN = 365
SMA_WINDOWS: tuple[int, ...] = (100, 150, 200)
CONFIRM_DAYS: tuple[int, ...] = (0, 3)
VOL_WINDOWS: tuple[int, ...] = (20, 30)
TARGET_ANN_VOL: tuple[float, ...] = (0.5, 0.6, 0.8)
LEVERAGE_CAPS: tuple[float, ...] = (1.0, 1.5)
#: Calmar must beat buy-and-hold by this ratio (e.g. 1.3 = 30% better) and
#: max drawdown must be at most this fraction of buy-and-hold's.
PASS_CALMAR_RATIO = 1.30
PASS_MAXDD_FRACTION = 0.75


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


def _regime_gate(close: pd.Series, sma_n: int, confirm: int) -> pd.Series:
    above = close > close.rolling(sma_n).mean()
    if confirm > 0:
        above = above.rolling(confirm).sum().eq(confirm)
    return above.fillna(False).astype(float)


def _weights(close: pd.Series, ret: pd.Series, *, sma_n, confirm, vol_w, target, cap) -> pd.Series:
    gate = _regime_gate(close, sma_n, confirm)
    pred_daily_vol = ret.rolling(vol_w).std(ddof=1)
    size = (target / (ANN**0.5) / pred_daily_vol).clip(lower=0.0, upper=cap)
    return (gate * size).shift(1)


def _subwindow_calmar(net: np.ndarray, base: np.ndarray, n: int = 3) -> list[dict]:
    b = np.linspace(0, len(net), n + 1, dtype=int)
    out = []
    for i in range(n):
        s, bb = _perf(net[b[i] : b[i + 1]]), _perf(base[b[i] : b[i + 1]])
        beats = (
            s["calmar"] is not None
            and bb["calmar"] is not None
            and s["calmar"] >= bb["calmar"] * PASS_CALMAR_RATIO
            and s["max_dd"] <= bb["max_dd"] * PASS_MAXDD_FRACTION
        )
        out.append(
            {
                "window": f"{i + 1}/{n}",
                "strat_calmar": s["calmar"],
                "buyhold_calmar": bb["calmar"],
                "strat_max_dd": s["max_dd"],
                "buyhold_max_dd": bb["max_dd"],
                "beats": bool(beats),
            }
        )
    return out


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Risk-managed long-core screen (statistical)")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2017-08-17")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--out", default=str(_BACKEND / "data" / "managed_long_core_research.json"))
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    fm = load_default_fill_model()
    cost = (fm.fee_bps + fm.slippage_bps) / 10_000.0

    payload: dict = {
        "start": args.start,
        "end": args.end,
        "one_way_cost": cost,
        "pass_calmar_ratio": PASS_CALMAR_RATIO,
        "pass_maxdd_fraction": PASS_MAXDD_FRACTION,
        "grid": {
            "sma_window": list(SMA_WINDOWS),
            "confirm_days": list(CONFIRM_DAYS),
            "vol_window": list(VOL_WINDOWS),
            "target_ann_vol": list(TARGET_ANN_VOL),
            "leverage_cap": list(LEVERAGE_CAPS),
        },
        "symbols": {},
    }

    per_symbol_pass: list[set] = []
    for symbol in [s.strip() for s in args.symbols.split(",")]:
        print(f"\n===== {symbol} =====", flush=True)
        df = await load_ohlcv(
            source="exchange", symbol=symbol, timeframe="1d", start=start, end=end
        )
        close = df["close"]
        ret = close.pct_change()
        base = ret.to_numpy()
        bh = _perf(base)
        print(f"  buy&hold: {bh}", flush=True)

        rows: list[dict] = []
        combos = itertools.product(
            SMA_WINDOWS, CONFIRM_DAYS, VOL_WINDOWS, TARGET_ANN_VOL, LEVERAGE_CAPS
        )
        for sma_n, confirm, vol_w, target, cap in combos:
            w = _weights(
                close, ret, sma_n=sma_n, confirm=confirm, vol_w=vol_w, target=target, cap=cap
            )
            gross = (w * ret).to_numpy()
            turn = w.diff().abs().fillna(w.abs()).to_numpy()
            net = gross - turn * cost
            valid = np.isfinite(net) & np.isfinite(base)
            nv, bv = net[valid], base[valid]
            perf = _perf(nv)
            bperf = _perf(bv)
            subs = _subwindow_calmar(nv, bv)
            sub_beats = sum(1 for s in subs if s["beats"])
            full_beats = (
                perf["calmar"] is not None
                and bperf["calmar"] is not None
                and perf["calmar"] >= bperf["calmar"] * PASS_CALMAR_RATIO
                and perf["max_dd"] <= bperf["max_dd"] * PASS_MAXDD_FRACTION
            )
            passes = bool(full_beats and sub_beats >= 2)
            rows.append(
                {
                    "sma_window": sma_n,
                    "confirm_days": confirm,
                    "vol_window": vol_w,
                    "target_ann_vol": target,
                    "leverage_cap": cap,
                    "avg_weight": round(float(np.nanmean(w.to_numpy())), 3),
                    "pct_in_market": round(float((_regime_gate(close, sma_n, confirm)).mean()), 3),
                    "ann_turnover": round(float(np.nansum(np.abs(np.diff(w.to_numpy())))), 1),
                    **{f"strat_{k}": v for k, v in perf.items()},
                    "buyhold_calmar": bperf["calmar"],
                    "buyhold_max_dd": bperf["max_dd"],
                    "buyhold_ann_return": bperf["ann_return"],
                    "subwindows_beat": f"{sub_beats}/3",
                    "subwindows": subs,
                    "passes": passes,
                }
            )

        rows.sort(
            key=lambda r: (r["strat_calmar"] is not None, r["strat_calmar"] or -9), reverse=True
        )
        print("  top-6 by Calmar (net of turnover):", flush=True)
        for r in rows[:6]:
            print(
                f"    SMA{r['sma_window']} c{r['confirm_days']} W{r['vol_window']} "
                f"tgt{r['target_ann_vol']} cap{r['leverage_cap']} inMkt={r['pct_in_market']} "
                f"| ret={r['strat_ann_return']} calmar={r['strat_calmar']} "
                f"maxDD={r['strat_max_dd']} sharpe={r['strat_sharpe']} "
                f"(BH ret={r['buyhold_ann_return']} calmar={r['buyhold_calmar']} "
                f"maxDD={r['buyhold_max_dd']}) sub={r['subwindows_beat']} "
                f"{'** PASS **' if r['passes'] else ''}",
                flush=True,
            )
        n_pass = sum(1 for r in rows if r["passes"])
        print(f"  PASS configs: {n_pass}/{len(rows)}", flush=True)
        per_symbol_pass.append(
            {
                (
                    r["sma_window"],
                    r["confirm_days"],
                    r["vol_window"],
                    r["target_ann_vol"],
                    r["leverage_cap"],
                )
                for r in rows
                if r["passes"]
            }
        )
        payload["symbols"][symbol] = {"buyhold": bh, "rows": rows, "pass_count": n_pass}

    shared = set.intersection(*per_symbol_pass) if per_symbol_pass else set()
    payload["shared_pass_configs"] = [
        f"SMA{a}/c{b}/W{c}/tgt{d}/cap{e}" for (a, b, c, d, e) in sorted(shared)
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    if shared:
        verdict = (
            f"PASS — {len(shared)} config(s) beat buy&hold Calmar by >={PASS_CALMAR_RATIO}x with "
            f"<= {PASS_MAXDD_FRACTION}x its max drawdown, on the full sample + >=2/3 subwindows, "
            f"on BOTH symbols: {payload['shared_pass_configs']} — port to CoreLongProvider + "
            "RiskManager sizing + regime gate, validate via ValidationHarness"
        )
    else:
        verdict = (
            "REJECT — no single config clears the Calmar/drawdown bar robustly on both symbols; "
            "the risk overlay does not make a clearly better vehicle than buy-and-hold"
        )
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
