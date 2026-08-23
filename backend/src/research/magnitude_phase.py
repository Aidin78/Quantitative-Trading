"""Phase 2 — Return/Magnitude Prediction.

Measures whether a backward-looking "quietness/strength" signal predicts the
*size* of the forward move (not its direction) — volatility clustering, not
directional edge. Every predictor reuses production indicator math.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from src.features.indicators import _adx_components, _atr_series, _bollinger_components
from src.research.signal_evaluator import DEFAULT_HORIZONS

MagnitudePredictor = Callable[[pd.DataFrame], pd.Series]

ROLLING_PERCENTILE_WINDOW = 200


def atr_pct(df: pd.DataFrame, *, period: int = 14) -> pd.Series:
    atr = _atr_series(df, period)
    return atr / df["close"] * 100


def atr_pct_percentile(
    df: pd.DataFrame, *, period: int = 14, window: int = ROLLING_PERCENTILE_WINDOW
) -> pd.Series:
    pct = atr_pct(df, period=period)
    return pct.rolling(window).apply(lambda x: (x.iloc[-1] > x).mean() * 100, raw=False)


def bb_width_pct(df: pd.DataFrame, *, period: int = 20, std_mult: float = 2.0) -> pd.Series:
    upper, middle, lower = _bollinger_components(df, period=period, std_mult=std_mult)
    return (upper - lower) / middle * 100


def bb_width_percentile(
    df: pd.DataFrame,
    *,
    period: int = 20,
    std_mult: float = 2.0,
    window: int = ROLLING_PERCENTILE_WINDOW,
) -> pd.Series:
    width = bb_width_pct(df, period=period, std_mult=std_mult)
    return width.rolling(window).apply(lambda x: (x.iloc[-1] > x).mean() * 100, raw=False)


def realized_vol(df: pd.DataFrame, *, window: int = 20) -> pd.Series:
    returns = df["close"].pct_change()
    return returns.rolling(window).std() * 100


def adx_level(df: pd.DataFrame, *, period: int = 14) -> pd.Series:
    adx, _plus_di, _minus_di = _adx_components(df, period=period)
    return adx


DEFAULT_PREDICTORS: dict[str, MagnitudePredictor] = {
    "atr_pct_14": atr_pct,
    "atr_pct_percentile_200": atr_pct_percentile,
    "bb_width_pct_20": bb_width_pct,
    "bb_width_percentile_200": bb_width_percentile,
    "realized_vol_20": realized_vol,
    "adx_level_14": adx_level,
}

#: Subset of DEFAULT_PREDICTORS already scaled 0-100 — the only ones usable as
#: a ``magnitude_filters`` gate in Phase 3, which compares against a percentile
#: threshold. Raw-scale predictors (e.g. atr_pct_14, in single-digit % units)
#: would compare nonsensically against a threshold like 70.
PERCENTILE_PREDICTORS: dict[str, MagnitudePredictor] = {
    "atr_pct_percentile_200": atr_pct_percentile,
    "bb_width_percentile_200": bb_width_percentile,
}


@dataclass(frozen=True)
class MagnitudeResult:
    name: str
    corr_absret_by_horizon: dict[int, float]
    corr_maxrange_by_horizon: dict[int, float]
    decile_table: pd.DataFrame


def _spearman_by_horizon(
    df_with_targets: pd.DataFrame,
    predictor: pd.Series,
    *,
    target_prefix: str,
    horizons: tuple[int, ...],
) -> dict[int, float]:
    result: dict[int, float] = {}
    for h in horizons:
        pair = pd.concat([predictor, df_with_targets[f"{target_prefix}_{h}"]], axis=1).dropna()
        if len(pair) > 1:
            result[h] = float(pair.corr(method="spearman").iloc[0, 1])
        else:
            result[h] = float("nan")
    return result


def decile_breakdown(
    df_with_targets: pd.DataFrame,
    predictor: pd.Series,
    *,
    horizon: int,
) -> pd.DataFrame:
    """Bucket the predictor into deciles and show mean forward magnitude per bucket.

    A monotonic increase across deciles is the visual signature of real,
    forward-usable predictive power (volatility clustering), distinct from a
    Spearman correlation number alone.
    """
    frame = pd.DataFrame(
        {
            "predictor": predictor,
            "fwd_absret": df_with_targets[f"fwd_absret_{horizon}"],
            "fwd_maxrange": df_with_targets[f"fwd_maxrange_{horizon}"],
        }
    ).dropna()
    frame["decile"] = pd.qcut(frame["predictor"], 10, labels=False, duplicates="drop")
    return (
        frame.groupby("decile")
        .agg(
            mean_fwd_absret=("fwd_absret", "mean"),
            mean_fwd_maxrange=("fwd_maxrange", "mean"),
            n=("fwd_absret", "size"),
        )
        .reset_index()
    )


def run_magnitude_phase(
    df_with_targets: pd.DataFrame,
    *,
    predictors: dict[str, MagnitudePredictor] | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    decile_horizon: int = 14,
) -> list[MagnitudeResult]:
    predictors = predictors or DEFAULT_PREDICTORS
    results: list[MagnitudeResult] = []
    for name, predictor_fn in predictors.items():
        predictor = predictor_fn(df_with_targets)
        corr_absret = _spearman_by_horizon(
            df_with_targets, predictor, target_prefix="fwd_absret", horizons=horizons
        )
        corr_maxrange = _spearman_by_horizon(
            df_with_targets, predictor, target_prefix="fwd_maxrange", horizons=horizons
        )
        deciles = decile_breakdown(df_with_targets, predictor, horizon=decile_horizon)
        results.append(
            MagnitudeResult(
                name=name,
                corr_absret_by_horizon=corr_absret,
                corr_maxrange_by_horizon=corr_maxrange,
                decile_table=deciles,
            )
        )
    return results
