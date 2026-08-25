"""Phase 1 — Direction Prediction.

Measures whether a backward-looking UP/DOWN candidate signal predicts the
*sign* of price movement over a forward horizon, against a 50% baseline.
Every candidate here reuses the platform's own indicator math
(``src.features.indicators``) rather than re-deriving it, so a finding here
transfers exactly to what a real provider would see.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features.indicators import (
    _adx_components,
    _supertrend_components,
    _volume_flow_components,
)
from src.features.indicators.market_structure import _find_confirmed_pivots
from src.research.signal_evaluator import DEFAULT_HORIZONS

DirectionSignal = Callable[[pd.DataFrame], pd.Series]

#: Pass threshold: a candidate must beat the 50% baseline by at least this many
#: percentage points, in at least ``PASS_MIN_HORIZONS`` of the tested horizons,
#: to be reported as worth carrying into Phase 2.
PASS_MARGIN_PCT = 2.0
PASS_MIN_HORIZONS = 2


def ema_compare(df: pd.DataFrame, *, fast: int = 12, slow: int = 26) -> pd.Series:
    """Current production trend definition (``context_deriver.py``): EMA(fast) vs EMA(slow)."""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    return pd.Series(np.where(ema_fast > ema_slow, "UP", "DOWN"), index=df.index)


def ema_compare_slow(df: pd.DataFrame, *, fast: int = 50, slow: int = 200) -> pd.Series:
    return ema_compare(df, fast=fast, slow=slow)


def supertrend_direction(
    df: pd.DataFrame, *, period: int = 10, multiplier: float = 3.0
) -> pd.Series:
    _line, direction = _supertrend_components(df, period=period, multiplier=multiplier)
    return pd.Series(np.where(direction > 0, "UP", "DOWN"), index=df.index)


def adx_directional_raw(df: pd.DataFrame, *, period: int = 14) -> pd.Series:
    """Raw +DI/-DI compare, no ADX-strength gate — known to whipsaw on its own."""
    _adx, plus_di, minus_di = _adx_components(df, period=period)
    return pd.Series(np.where(plus_di > minus_di, "UP", "DOWN"), index=df.index)


def adx_directional_gated(
    df: pd.DataFrame, *, period: int = 14, min_adx: float = 20.0
) -> pd.Series:
    """+DI/-DI direction, held over from the prior bar while ADX < min_adx."""
    adx, plus_di, minus_di = _adx_components(df, period=period)
    raw_dir = np.where(plus_di > minus_di, 1, -1)
    gated = raw_dir.copy()
    adx_values = adx.to_numpy()
    for i in range(1, len(gated)):
        if np.isnan(adx_values[i]) or adx_values[i] < min_adx:
            gated[i] = gated[i - 1]
    return pd.Series(np.where(gated > 0, "UP", "DOWN"), index=df.index)


def market_structure_bias(df: pd.DataFrame, *, pivot_bars: int = 5) -> pd.Series:
    """Vectorized bias series (HH/HL vs LH/LL), reusing the production pivot helper.

    ``_market_structure_latest`` only returns the latest scalar bias, and
    calling ``_find_confirmed_pivots`` once per bar would be O(n^2) — each
    call re-scans the whole array. Instead, confirmed pivots over the full
    history are found once (``up_to_index=n-1``, the maximal range), then the
    bias series is built by forward-filling the bias verdict as of each
    pivot's *confirmation* index (``i + pivot_bars``, matching how
    ``_structure_bos``/production code learns about a pivot only after it is
    confirmed) — so no bar ever sees a pivot before it would in a live/replay
    run.
    """
    n = len(df)
    highs, lows = _find_confirmed_pivots(df, pivot_bars=pivot_bars, up_to_index=n - 1)

    bias = np.zeros(n)
    prev_bias = 0.0

    def _events(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
        return [(i + pivot_bars, price) for i, price in points]

    high_events = _events(highs)
    low_events = _events(lows)

    hi = 0
    li = 0
    last_high2 = last_high1 = None
    last_low2 = last_low1 = None
    for t in range(n):
        while hi < len(high_events) and high_events[hi][0] <= t:
            last_high2, last_high1 = last_high1, high_events[hi][1]
            hi += 1
        while li < len(low_events) and low_events[li][0] <= t:
            last_low2, last_low1 = last_low1, low_events[li][1]
            li += 1
        if last_high2 is not None and last_low2 is not None:
            if last_high1 > last_high2 and last_low1 > last_low2:
                prev_bias = 1.0
            elif last_high1 < last_high2 and last_low1 < last_low2:
                prev_bias = -1.0
        bias[t] = prev_bias

    return pd.Series(np.where(bias >= 0, "UP", "DOWN"), index=df.index)


def volume_order_flow_direction(
    df: pd.DataFrame, *, period: int = 20, min_cmf: float = 0.05, min_volume_ratio: float = 1.2
) -> pd.Series:
    """Order-flow-hypothesis direction: distinct from every other candidate here
    (all of which are trend-following variants of a price-derived line/pivot).
    Mirrors ``providers.volume_order_flow.VolumeOrderFlowProvider``'s BUY/SELL
    gate exactly (bullish: CMF >= min_cmf AND volume_ratio >= min_volume_ratio;
    bearish: the mirror) so a finding here transfers to what that real provider
    would see -- but returns UP/DOWN only (no HOLD, no price-alignment filter,
    no confidence/min_confidence), since ``DirectionSignal`` in this research
    module is binary and Phase 1 measures raw directional accuracy before any
    gating is layered on. On a weak-flow bar (CMF or volume below threshold on
    both sides), holds over the last confirmed direction (bar 1 defaults UP)
    rather than picking an arbitrary side, the same "carry forward" shape
    ``adx_directional_gated`` uses for its own weak-signal bars.
    """
    cmf, volume_ratio = _volume_flow_components(df, period=period)
    volume_confirmed = (volume_ratio >= min_volume_ratio).to_numpy()
    bullish = (cmf.to_numpy() >= min_cmf) & volume_confirmed
    bearish = (cmf.to_numpy() <= -min_cmf) & volume_confirmed

    direction = np.ones(len(df))
    for i in range(len(df)):
        if bullish[i]:
            direction[i] = 1
        elif bearish[i]:
            direction[i] = -1
        elif i > 0:
            direction[i] = direction[i - 1]
    return pd.Series(np.where(direction > 0, "UP", "DOWN"), index=df.index)


DEFAULT_CANDIDATES: dict[str, DirectionSignal] = {
    "ema_compare_12_26 (current production)": ema_compare,
    "ema_compare_50_200 (slow)": ema_compare_slow,
    "supertrend_direction_10_3.0": supertrend_direction,
    "adx_directional_raw_14": adx_directional_raw,
    "adx_directional_gated_14_20": adx_directional_gated,
    "market_structure_bias_5": market_structure_bias,
    "volume_order_flow_20": volume_order_flow_direction,
}


@dataclass(frozen=True)
class DirectionResult:
    name: str
    accuracy_by_horizon: dict[int, float]
    flips: int
    median_run_len: float
    passes_threshold: bool


def _run_lengths(signal: pd.Series) -> pd.Series:
    change_id = (signal != signal.shift(1)).cumsum()
    return signal.groupby(change_id).size()


def evaluate_direction_candidate(
    df_with_targets: pd.DataFrame,
    signal: pd.Series,
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> tuple[dict[int, float], int, float]:
    accuracy: dict[int, float] = {}
    for h in horizons:
        fwd = df_with_targets[f"fwd_ret_{h}"]
        valid = fwd.notna() & signal.notna()
        pred_up = (signal == "UP") & valid
        pred_down = (signal == "DOWN") & valid
        correct = ((pred_up & (fwd > 0)) | (pred_down & (fwd < 0))).sum()
        total = int(valid.sum())
        accuracy[h] = (correct / total * 100) if total else float("nan")
    flips = int((signal != signal.shift(1)).sum())
    median_run_len = float(_run_lengths(signal).median())
    return accuracy, flips, median_run_len


def run_direction_phase(
    df_with_targets: pd.DataFrame,
    *,
    candidates: dict[str, DirectionSignal] | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[DirectionResult]:
    candidates = candidates or DEFAULT_CANDIDATES
    results: list[DirectionResult] = []
    for name, signal_fn in candidates.items():
        signal = signal_fn(df_with_targets)
        accuracy, flips, median_run_len = evaluate_direction_candidate(
            df_with_targets, signal, horizons=horizons
        )
        beats_baseline = sum(1 for acc in accuracy.values() if acc >= 50.0 + PASS_MARGIN_PCT)
        results.append(
            DirectionResult(
                name=name,
                accuracy_by_horizon=accuracy,
                flips=flips,
                median_run_len=median_run_len,
                passes_threshold=beats_baseline >= PASS_MIN_HORIZONS,
            )
        )
    return results
