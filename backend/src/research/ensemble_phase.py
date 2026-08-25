"""Phase 3c — Signal ensembles: does agreement across multiple independent
direction signals produce a more regime-stable edge than any one signal alone?

Motivation: ``docs/development/candidate-stability-findings.md`` and the
follow-up windowing experiment (``run_candidate_windowing_experiment.py``)
both concluded that ``ema_compare_50_200 + atr_pct_percentile_200``'s
instability is driven by which market regime happens to land in which
sub-window, not by the percentile threshold or the number of windows used to
measure it — neither more sub-windows nor a threshold band fixed it. This
module tests the platform's own answer to that class of problem: the
Engine-Centric ``Aggregator`` combines multiple independent Signal Providers
by (weighted) majority vote specifically so that one provider's bad regime is
outvoted by others that don't share its blind spot. This asks the same
question one layer up in the research pipeline, before anything is ported to
a real provider: does requiring >=N of the Phase-1 direction candidates
(``direction_phase.DEFAULT_CANDIDATES``) to agree produce a signal whose edge
survives being sliced into sub-windows, where no single candidate did?

Never touches the Decision Engine, a provider, or execution — reuses
``direction_phase``'s existing candidate functions and produces a
``BaseSignal``-shaped ("UP"/"DOWN"/"HOLD" per bar) callable that plugs
directly into ``stability_phase.evaluate_candidate_stability`` and
``sweep_percentile_thresholds`` without changing either.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from src.research.direction_phase import DEFAULT_CANDIDATES, DirectionSignal

#: A vote of "UP"/"DOWN" per member signal; "HOLD" is never produced by a
#: DirectionSignal itself (direction_phase's candidates always emit UP/DOWN),
#: so ensemble disagreement is the only source of "HOLD" in the combined series.
EnsembleSignal = Callable[[pd.DataFrame], pd.Series]


def make_ensemble_signal(
    member_names: tuple[str, ...],
    *,
    min_agreeing: int,
    candidates: Mapping[str, DirectionSignal] | None = None,
) -> EnsembleSignal:
    """Build a majority-vote ensemble over named Phase-1 direction candidates.

    Mirrors ``engine.aggregator``'s "at least N agreeing, side = the
    majority" shape (unweighted here — Phase-1 candidates have no
    provider-level ``weight`` config to reuse) applied to research-only
    direction series instead of live ``StrategySignal`` objects. A bar votes
    "HOLD" (excluded from ``_trade_pnls`` the same way real HOLD is excluded
    from aggregation) whenever fewer than ``min_agreeing`` members agree on a
    single side, or the UP/DOWN vote is tied.
    """
    candidates = candidates or DEFAULT_CANDIDATES
    unknown = set(member_names) - set(candidates)
    if unknown:
        raise ValueError(f"Unknown direction candidate(s): {sorted(unknown)}")
    if len(member_names) < 2:
        raise ValueError("An ensemble needs at least 2 member signals")
    if not (1 <= min_agreeing <= len(member_names)):
        raise ValueError("min_agreeing must be between 1 and len(member_names)")

    def _ensemble(df: pd.DataFrame) -> pd.Series:
        votes = pd.DataFrame({name: candidates[name](df) for name in member_names}, index=df.index)
        up_count = (votes == "UP").sum(axis=1)
        down_count = (votes == "DOWN").sum(axis=1)
        side = np.select(
            [
                (up_count >= min_agreeing) & (up_count > down_count),
                (down_count >= min_agreeing) & (down_count > up_count),
            ],
            ["UP", "DOWN"],
            default="HOLD",
        )
        return pd.Series(side, index=df.index)

    return _ensemble


@dataclass(frozen=True)
class EnsembleAgreementStats:
    """How often an ensemble reaches a directional vote, and its raw (ungated,
    unfiltered) forward-return accuracy — the ensemble-level analogue of
    ``direction_phase.DirectionResult``, computed before any magnitude gate.
    """

    member_names: tuple[str, ...]
    min_agreeing: int
    active_bars: int
    total_bars: int
    active_share: float
    accuracy_by_horizon: dict[int, float]


def evaluate_ensemble_agreement(
    df_with_targets: pd.DataFrame,
    ensemble: EnsembleSignal,
    *,
    member_names: tuple[str, ...],
    min_agreeing: int,
    horizons: tuple[int, ...],
) -> EnsembleAgreementStats:
    """Raw directional accuracy of an ensemble vote, mirroring
    ``direction_phase.evaluate_direction_candidate`` but reporting
    ``active_share`` too — requiring agreement necessarily produces fewer
    directional bars than any single member, and that trade-off (fewer, but
    hopefully better, signals) needs to be visible, not just accuracy.
    """
    signal = ensemble(df_with_targets)
    total = len(signal)
    active_mask = signal != "HOLD"
    active = int(active_mask.sum())

    accuracy: dict[int, float] = {}
    for h in horizons:
        fwd = df_with_targets[f"fwd_ret_{h}"]
        valid = fwd.notna() & active_mask
        pred_up = (signal == "UP") & valid
        pred_down = (signal == "DOWN") & valid
        correct = ((pred_up & (fwd > 0)) | (pred_down & (fwd < 0))).sum()
        n_valid = int(valid.sum())
        accuracy[h] = (correct / n_valid * 100) if n_valid else float("nan")

    return EnsembleAgreementStats(
        member_names=member_names,
        min_agreeing=min_agreeing,
        active_bars=active,
        total_bars=total,
        active_share=(active / total * 100) if total else 0.0,
        accuracy_by_horizon=accuracy,
    )


def default_ensemble_grid(
    candidates: Mapping[str, DirectionSignal] | None = None,
    *,
    sizes: tuple[int, ...] = (2, 3),
) -> dict[str, tuple[tuple[str, ...], int]]:
    """Every unordered combination of Phase-1 candidates at each size in
    ``sizes``, paired with a "require unanimous agreement" ``min_agreeing``
    (i.e. ``min_agreeing == len(combo)``) — the strictest, most
    regime-orthogonal vote shape, and the natural first grid to sweep before
    trying partial-agreement (``min_agreeing < len(combo)``) variants.

    Returns a dict keyed by a human-readable combo label (e.g.
    ``"ema_compare_12_26+supertrend_direction_10_3.0 (unanimous 2/2)"``) so
    results are easy to print/report without re-deriving the label elsewhere.
    """
    names = tuple((candidates or DEFAULT_CANDIDATES).keys())
    grid: dict[str, tuple[tuple[str, ...], int]] = {}
    for size in sizes:
        for combo in combinations(names, size):
            short = tuple(n.split(" ")[0] for n in combo)
            label = f"{'+'.join(short)} (unanimous {size}/{size})"
            grid[label] = (combo, size)
    return grid
