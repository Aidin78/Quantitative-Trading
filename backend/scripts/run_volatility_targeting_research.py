#!/usr/bin/env python3
"""Screen the one hypothesis class the whole investigation still points to:
volatility-regime position sizing (NOT direction prediction).

Context: every directional signal has been rejected (classic TA on 1h/4h/1d,
ensembles, order-flow, the ADX-1d sweep, funding rate) — see
docs/development/{edge-investigation,candidate-stability,funding-signal}-findings.md
and provider-edge-htf-experiment-plan.md §10. The ONE positive statistical
result in the entire pipeline is Phase 2's finding that magnitude /
volatility is autocorrelated (volatility clustering) for BTC. Direction is
unpredictable; magnitude is not.

You cannot trade magnitude for a side, but you can size on it: scale
long exposure inversely to predicted volatility. The classic result is that
this raises the *risk-adjusted* return (Sharpe) and cuts drawdown of a
long-only position, because vol spikes cluster around drawdowns (leverage
effect). This script tests exactly that, statistically, before anything is
built into the RiskManager / sizing layer.

Rigor (learned from the funding screen's false positive): the baseline is
buy-and-hold, the metric is SHARPE and MAX DRAWDOWN (both scale-invariant,
so they are not gamed by the sizing overlay changing average exposure), the
result must survive turnover cost from ``load_default_fill_model``, hold in
>=2/3 chronological subwindows, and hold on BOTH BTC and ETH.

Look-ahead: predicted vol at bar t uses only returns r[t-W+1 .. t] (all known
at t's close); the weight w[t] is applied to r[t+1]. No future bar is read.
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

ANN = 365  # crypto trades every day
VOL_WINDOWS: tuple[int, ...] = (10, 20, 30, 60)
TARGET_ANN_VOL: tuple[float, ...] = (0.40, 0.60, 0.80)
LEVERAGE_CAPS: tuple[float, ...] = (1.0, 2.0)
#: A sizing overlay must beat buy-and-hold Sharpe by at least this, after
#: turnover cost, on the full sample AND in >=2 of 3 subwindows.
PASS_SHARPE_MARGIN = 0.15


def _one_way_cost() -> float:
    fm = load_default_fill_model()
    return (fm.fee_bps + fm.slippage_bps) / 10_000.0


def _perf(daily_returns: np.ndarray) -> dict:
    """Annualized return / vol / Sharpe / max-drawdown / Calmar for a daily return series."""
    r = daily_returns[np.isfinite(daily_returns)]
    if r.size < 30:
        return {k: None for k in ("ann_return", "ann_vol", "sharpe", "max_dd", "calmar")}
    mean, std = float(r.mean()), float(r.std(ddof=1))
    ann_return = mean * ANN
    ann_vol = std * (ANN**0.5)
    sharpe = (mean / std * (ANN**0.5)) if std > 0 else 0.0
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    max_dd = float((1.0 - equity / peak).max())
    calmar = ann_return / max_dd if max_dd > 0 else None
    return {
        "ann_return": round(ann_return, 4),
        "ann_vol": round(ann_vol, 4),
        "sharpe": round(sharpe, 3),
        "max_dd": round(max_dd, 4),
        "calmar": round(calmar, 3) if calmar is not None else None,
    }


def _vol_target_weights(
    ret: pd.Series, window: int, target_ann_vol: float, cap: float
) -> pd.Series:
    """w[t] = target / predicted_vol[t], from returns up to and including t; clipped [0, cap]."""
    pred_daily_vol = ret.rolling(window).std(ddof=1)
    target_daily_vol = target_ann_vol / (ANN**0.5)
    w = (target_daily_vol / pred_daily_vol).clip(lower=0.0, upper=cap)
    return w.shift(1)  # weight decided at t-1 close is held over day t


def _strategy_returns(ret: pd.Series, w: pd.Series, cost: float) -> np.ndarray:
    gross = (w * ret).to_numpy()
    turn = w.diff().abs().fillna(w.abs()).to_numpy()
    net = gross - turn * cost
    return net


def _subwindow_sharpes(net: np.ndarray, base: np.ndarray, n: int = 3) -> list[dict]:
    bounds = np.linspace(0, len(net), n + 1, dtype=int)
    out = []
    for i in range(n):
        lo, hi = bounds[i], bounds[i + 1]
        sp = _perf(net[lo:hi])["sharpe"]
        bp = _perf(base[lo:hi])["sharpe"]
        out.append(
            {
                "window": f"{i + 1}/{n}",
                "strat_sharpe": sp,
                "buyhold_sharpe": bp,
                "beats": (sp is not None and bp is not None and sp - bp >= PASS_SHARPE_MARGIN),
            }
        )
    return out


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Volatility-targeting sizing screen (statistical)")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--start", default="2017-08-17")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument(
        "--out", default=str(_BACKEND / "data" / "volatility_targeting_research.json")
    )
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    cost = _one_way_cost()

    payload: dict = {
        "start": args.start,
        "end": args.end,
        "timeframe": args.timeframe,
        "annualization_days": ANN,
        "one_way_cost": cost,
        "grid": {
            "vol_window": list(VOL_WINDOWS),
            "target_ann_vol": list(TARGET_ANN_VOL),
            "leverage_cap": list(LEVERAGE_CAPS),
        },
        "pass_sharpe_margin": PASS_SHARPE_MARGIN,
        "symbols": {},
    }

    per_symbol_pass_configs: list[set] = []
    for symbol in [s.strip() for s in args.symbols.split(",")]:
        print(f"\n===== {symbol} {args.timeframe} =====", flush=True)
        df = await load_ohlcv(
            source="exchange",
            symbol=symbol,
            timeframe=args.timeframe,
            start=start,
            end=end,
        )
        ret = df["close"].pct_change().rename("ret")
        buyhold = ret.to_numpy()
        bh = _perf(buyhold)
        print(
            f"  {len(df)} bars | buy&hold: ann_ret={bh['ann_return']} "
            f"sharpe={bh['sharpe']} maxDD={bh['max_dd']}",
            flush=True,
        )

        rows: list[dict] = []
        for window, target, cap in itertools.product(VOL_WINDOWS, TARGET_ANN_VOL, LEVERAGE_CAPS):
            w = _vol_target_weights(ret, window, target, cap)
            net = _strategy_returns(ret, w, cost)
            # align: drop leading NaN region where weight is undefined
            valid = np.isfinite(net) & np.isfinite(buyhold)
            net_v, base_v = net[valid], buyhold[valid]
            perf = _perf(net_v)
            base_perf = _perf(base_v)
            subs = _subwindow_sharpes(net_v, base_v)
            sub_beats = sum(1 for s in subs if s["beats"])
            full_beats = (
                perf["sharpe"] is not None
                and base_perf["sharpe"] is not None
                and perf["sharpe"] - base_perf["sharpe"] >= PASS_SHARPE_MARGIN
            )
            passes = bool(full_beats and sub_beats >= 2)
            rows.append(
                {
                    "vol_window": window,
                    "target_ann_vol": target,
                    "leverage_cap": cap,
                    "avg_weight": round(float(np.nanmean(w.to_numpy())), 3),
                    "ann_turnover": round(float(np.nansum(w.diff().abs()) / (len(w) / ANN)), 1),
                    **{f"strat_{k}": v for k, v in perf.items()},
                    "buyhold_sharpe": base_perf["sharpe"],
                    "buyhold_max_dd": base_perf["max_dd"],
                    "sharpe_gain": (
                        round(perf["sharpe"] - base_perf["sharpe"], 3)
                        if perf["sharpe"] is not None and base_perf["sharpe"] is not None
                        else None
                    ),
                    "subwindows_beat": f"{sub_beats}/3",
                    "subwindows": subs,
                    "passes": passes,
                }
            )

        rows.sort(
            key=lambda r: (r["sharpe_gain"] is not None, r["sharpe_gain"] or -9), reverse=True
        )
        print("  top-5 by Sharpe gain vs buy&hold (net of turnover):", flush=True)
        for r in rows[:5]:
            print(
                f"    W={r['vol_window']:<2} tgt={r['target_ann_vol']} cap={r['leverage_cap']} "
                f"| strat sharpe={r['strat_sharpe']} maxDD={r['strat_max_dd']} "
                f"(BH {r['buyhold_sharpe']}/{r['buyhold_max_dd']}) "
                f"gain={r['sharpe_gain']} sub={r['subwindows_beat']} "
                f"{'** PASS **' if r['passes'] else ''}",
                flush=True,
            )
        n_pass = sum(1 for r in rows if r["passes"])
        print(f"  PASS configs: {n_pass}/{len(rows)}", flush=True)
        pass_cfgs = {
            (r["vol_window"], r["target_ann_vol"], r["leverage_cap"]) for r in rows if r["passes"]
        }
        per_symbol_pass_configs.append(pass_cfgs)
        payload["symbols"][symbol] = {
            "buyhold": bh,
            "rows": rows,
            "pass_count": n_pass,
        }

    shared = set.intersection(*per_symbol_pass_configs) if per_symbol_pass_configs else set()
    payload["shared_pass_configs"] = sorted(f"W{w}/tgt{t}/cap{c}" for (w, t, c) in shared)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    if not shared:
        verdict = (
            "REJECT — no (vol_window, target, cap) config beats buy&hold Sharpe by "
            f">={PASS_SHARPE_MARGIN} on the full sample + >=2/3 subwindows on BOTH symbols"
        )
    else:
        verdict = (
            f"PASS — {len(shared)} config(s) beat buy&hold Sharpe robustly on both symbols: "
            f"{payload['shared_pass_configs']} — take to a real RiskManager-sizing backtest"
        )
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
