"""Phase 3 — Threshold Classification.

Phase 1 found no direction-prediction edge; Phase 2 found real magnitude
(volatility-clustering) edge. Since magnitude alone carries no side, this
phase does NOT build a standalone LONG/SHORT/NO-TRADE classifier from
direction. Instead it tests the one shape that survives both findings: does
gating an *existing* signal (its own direction, whatever the source) on a
magnitude/volatility threshold change trade quality? This directly produces a
``provider_overrides``-shaped threshold that Phase 4 (the existing
``provider_edge_scorecard``) can validate under real fees/slippage/sizing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.execution.config import load_default_fill_model
from src.research.signal_evaluator import DEFAULT_HORIZONS

BaseSignal = Callable[[pd.DataFrame], pd.Series]
MagnitudeFilter = Callable[[pd.DataFrame], pd.Series]

#: A gated variant must improve win-rate by at least this many percentage
#: points over the ungated baseline, at the evaluated horizon, to be reported
#: as a Phase-4 candidate.
MIN_WIN_RATE_IMPROVEMENT_PP = 2.0
MIN_TRADES_FOR_COMPARISON = 30


@dataclass(frozen=True)
class TradeStats:
    """Trade-level stats derived from a signed PnL vector (one entry per 'trade').

    ``pnl`` here is a directional forward-return percentage (see
    ``_trade_pnls``), not a real fee/slippage-adjusted fill — see
    ``net_of_fees`` for the fee/slippage-approximated variant.

    ``max_drawdown_pct`` is peak-to-trough on a *cumulative-sum* of per-trade
    percentage returns (flat position sizing, no compounding, no equity
    base) — it can exceed 100 with enough overlapping/back-to-back trades.
    This is a relative-ranking tool for comparing candidates, not the
    platform's real equity-based ``max_drawdown_pct`` from
    ``validation.metrics.compute_outcome_metrics`` (compounding, dollar
    equity curve) — do not quote this number as an expected account
    drawdown.
    """

    trades: int
    win_rate: float
    expectancy: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_drawdown_pct: float


_EMPTY_TRADE_STATS = TradeStats(
    trades=0,
    win_rate=float("nan"),
    expectancy=float("nan"),
    profit_factor=float("nan"),
    avg_win=float("nan"),
    avg_loss=float("nan"),
    max_drawdown_pct=float("nan"),
)


def _trade_pnls(
    df_with_targets: pd.DataFrame,
    signal: pd.Series,
    *,
    horizon: int,
    mask: pd.Series | None = None,
) -> np.ndarray:
    """Signed PnL (%) for each active bar: +fwd_ret for UP, -fwd_ret for DOWN.

    Reuses the same look-ahead-safe ``fwd_ret_{horizon}`` column every other
    function in this package reads from (see ``signal_evaluator``'s
    look-ahead rule) — never recomputed here.
    """
    fwd = df_with_targets[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna()
    if mask is not None:
        active = active & mask
    direction = np.where(signal == "UP", 1.0, -1.0)
    pnl = fwd.to_numpy() * direction
    return pnl[active.to_numpy()]


def _trade_stats_from_pnls(pnls: np.ndarray) -> TradeStats:
    if pnls.size == 0:
        return _EMPTY_TRADE_STATS
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    win_rate = wins.size / pnls.size * 100
    expectancy = float(pnls.mean())
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit else 0.0
    )
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(losses.mean()) if losses.size else 0.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    drawdown = peak - equity
    max_drawdown_pct = float(drawdown.max())

    return TradeStats(
        trades=int(pnls.size),
        win_rate=win_rate,
        expectancy=expectancy,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_drawdown_pct=max_drawdown_pct,
    )


def _net_of_fees(pnls: np.ndarray) -> TradeStats:
    """Approximate round-trip fee/slippage drag using the platform's real default FillModel.

    This is a pre-screening approximation (a flat bps haircut per trade), not
    an order-level fill simulation — the real cost depends on entry/exit fill
    price and slippage direction, which only ``ValidationHarness`` computes.
    """
    fill_model = load_default_fill_model()
    round_trip_cost_pct = 2 * (fill_model.fee_bps + fill_model.slippage_bps) / 100
    net_pnls = pnls - round_trip_cost_pct
    return _trade_stats_from_pnls(net_pnls)


@dataclass(frozen=True)
class ClassificationResult:
    base_signal: str
    filter_name: str
    filter_threshold_percentile: float
    horizon: int
    baseline_trades: int
    baseline_win_rate: float
    filtered_trades: int
    filtered_win_rate: float
    win_rate_improvement_pp: float
    passes_threshold: bool
    baseline_stats: TradeStats = field(default_factory=lambda: _EMPTY_TRADE_STATS)
    filtered_stats: TradeStats = field(default_factory=lambda: _EMPTY_TRADE_STATS)
    baseline_stats_net_fees: TradeStats = field(default_factory=lambda: _EMPTY_TRADE_STATS)
    filtered_stats_net_fees: TradeStats = field(default_factory=lambda: _EMPTY_TRADE_STATS)


def _directional_win_rate(
    df_with_targets: pd.DataFrame,
    signal: pd.Series,
    *,
    horizon: int,
    mask: pd.Series | None = None,
) -> tuple[int, float]:
    """A 'trade' is any bar where signal is UP or DOWN; a 'win' is fwd_ret agreeing with it."""
    fwd = df_with_targets[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna()
    if mask is not None:
        active = active & mask
    if not active.any():
        return 0, float("nan")
    pred_up = (signal == "UP") & active
    pred_down = (signal == "DOWN") & active
    wins = ((pred_up & (fwd > 0)) | (pred_down & (fwd < 0))).sum()
    trades = int(active.sum())
    return trades, (wins / trades * 100) if trades else float("nan")


def evaluate_magnitude_gate(
    df_with_targets: pd.DataFrame,
    *,
    base_signal_name: str,
    base_signal: pd.Series,
    filter_name: str,
    filter_series: pd.Series,
    percentile_threshold: float,
    horizon: int = 14,
) -> ClassificationResult:
    """Compare win-rate of ``base_signal`` unfiltered vs. gated on a magnitude percentile.

    ``filter_series`` is expected to already be a rolling percentile (0-100,
    e.g. from ``magnitude_phase.atr_pct_percentile``); ``percentile_threshold``
    keeps only bars where it's at or above that value (i.e. "volatility is
    currently elevated relative to its own recent history").
    """
    baseline_trades, baseline_win_rate = _directional_win_rate(
        df_with_targets, base_signal, horizon=horizon
    )
    gate_mask = filter_series >= percentile_threshold
    filtered_trades, filtered_win_rate = _directional_win_rate(
        df_with_targets, base_signal, horizon=horizon, mask=gate_mask
    )

    improvement = (
        filtered_win_rate - baseline_win_rate
        if not (np.isnan(filtered_win_rate) or np.isnan(baseline_win_rate))
        else float("nan")
    )
    passes = bool(
        filtered_trades >= MIN_TRADES_FOR_COMPARISON
        and not np.isnan(improvement)
        and improvement >= MIN_WIN_RATE_IMPROVEMENT_PP
    )

    baseline_pnls = _trade_pnls(df_with_targets, base_signal, horizon=horizon)
    filtered_pnls = _trade_pnls(df_with_targets, base_signal, horizon=horizon, mask=gate_mask)

    return ClassificationResult(
        base_signal=base_signal_name,
        filter_name=filter_name,
        filter_threshold_percentile=percentile_threshold,
        horizon=horizon,
        baseline_trades=baseline_trades,
        baseline_win_rate=baseline_win_rate,
        filtered_trades=filtered_trades,
        filtered_win_rate=filtered_win_rate,
        win_rate_improvement_pp=improvement,
        passes_threshold=passes,
        baseline_stats=_trade_stats_from_pnls(baseline_pnls),
        filtered_stats=_trade_stats_from_pnls(filtered_pnls),
        baseline_stats_net_fees=_net_of_fees(baseline_pnls),
        filtered_stats_net_fees=_net_of_fees(filtered_pnls),
    )


def run_classification_phase(
    df_with_targets: pd.DataFrame,
    *,
    base_signals: dict[str, BaseSignal],
    magnitude_filters: dict[str, MagnitudeFilter],
    percentile_thresholds: tuple[float, ...] = (50.0, 70.0, 90.0),
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[ClassificationResult]:
    results: list[ClassificationResult] = []
    for base_name, base_fn in base_signals.items():
        base_signal = base_fn(df_with_targets)
        for filter_name, filter_fn in magnitude_filters.items():
            filter_series = filter_fn(df_with_targets)
            for threshold in percentile_thresholds:
                for horizon in horizons:
                    results.append(
                        evaluate_magnitude_gate(
                            df_with_targets,
                            base_signal_name=base_name,
                            base_signal=base_signal,
                            filter_name=filter_name,
                            filter_series=filter_series,
                            percentile_threshold=threshold,
                            horizon=horizon,
                        )
                    )
    return results
