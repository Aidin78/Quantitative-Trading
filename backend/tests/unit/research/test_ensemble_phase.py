from __future__ import annotations

import pandas as pd
import pytest

from src.research.direction_phase import DEFAULT_CANDIDATES, ema_compare, ema_compare_slow
from src.research.ensemble_phase import (
    default_ensemble_grid,
    evaluate_ensemble_agreement,
    make_ensemble_signal,
)
from src.research.signal_evaluator import compute_forward_targets
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def df_with_targets() -> pd.DataFrame:
    df = make_sample_ohlcv(bars=300)
    return compute_forward_targets(df, horizons=(4, 8, 14))


def test_make_ensemble_signal_rejects_unknown_member() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        make_ensemble_signal(
            ("ema_compare_12_26 (current production)", "nonexistent"), min_agreeing=2
        )


def test_make_ensemble_signal_rejects_single_member() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        make_ensemble_signal(("ema_compare_12_26 (current production)",), min_agreeing=1)


def test_make_ensemble_signal_rejects_invalid_min_agreeing() -> None:
    names = ("ema_compare_12_26 (current production)", "ema_compare_50_200 (slow)")
    with pytest.raises(ValueError, match="min_agreeing"):
        make_ensemble_signal(names, min_agreeing=3)


def test_two_identical_signals_unanimous_matches_either_alone(
    df_with_targets: pd.DataFrame,
) -> None:
    """A degenerate but useful sanity check: an ensemble of two DIFFERENT wrappers
    around the same underlying signal (both keys map to ema_compare via a custom
    candidates dict) must agree everywhere, so unanimous-2 should equal the signal
    itself bar-for-bar -- proving the vote-counting logic isn't off by one.
    """
    candidates = {"a": ema_compare, "b": ema_compare}
    ensemble = make_ensemble_signal(("a", "b"), min_agreeing=2, candidates=candidates)
    combined = ensemble(df_with_targets)
    solo = ema_compare(df_with_targets)
    assert (combined == solo).all()


def test_unanimous_ensemble_holds_on_disagreement(df_with_targets: pd.DataFrame) -> None:
    """Two genuinely different signals (fast vs slow EMA cross) must disagree on
    at least some bars in a long enough series -- unanimous agreement (min_agreeing=2)
    must emit HOLD on exactly those disagreement bars, never a side neither voted for.
    """
    candidates = {"fast": ema_compare, "slow": ema_compare_slow}
    ensemble = make_ensemble_signal(("fast", "slow"), min_agreeing=2, candidates=candidates)
    combined = ensemble(df_with_targets)
    fast_signal = ema_compare(df_with_targets)
    slow_signal = ema_compare_slow(df_with_targets)

    agree_mask = fast_signal == slow_signal
    assert not agree_mask.all(), "fixture must contain at least one disagreement bar"
    assert (combined[agree_mask] == fast_signal[agree_mask]).all()
    assert (combined[~agree_mask] == "HOLD").all()


def test_evaluate_ensemble_agreement_active_share_reflects_hold_bars(
    df_with_targets: pd.DataFrame,
) -> None:
    candidates = {"fast": ema_compare, "slow": ema_compare_slow}
    ensemble = make_ensemble_signal(("fast", "slow"), min_agreeing=2, candidates=candidates)
    stats = evaluate_ensemble_agreement(
        df_with_targets,
        ensemble,
        member_names=("fast", "slow"),
        min_agreeing=2,
        horizons=(4, 8),
    )
    assert stats.total_bars == len(df_with_targets)
    assert 0 < stats.active_bars < stats.total_bars
    assert stats.active_share == pytest.approx(stats.active_bars / stats.total_bars * 100)
    assert set(stats.accuracy_by_horizon) == {4, 8}


def test_default_ensemble_grid_size_2_covers_all_pairs() -> None:
    grid = default_ensemble_grid(DEFAULT_CANDIDATES, sizes=(2,))
    n = len(DEFAULT_CANDIDATES)
    expected_pairs = n * (n - 1) // 2
    assert len(grid) == expected_pairs
    for member_names, min_agreeing in grid.values():
        assert len(member_names) == 2
        assert min_agreeing == 2
        assert all(name in DEFAULT_CANDIDATES for name in member_names)


def test_default_ensemble_grid_labels_are_unique() -> None:
    grid = default_ensemble_grid(DEFAULT_CANDIDATES, sizes=(2, 3))
    assert len(grid) == len(set(grid.keys()))
