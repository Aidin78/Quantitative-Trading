from __future__ import annotations

import pytest

from src.validation.optimizer import (
    OptimizationSpace,
    TrialResult,
    composite_score,
    compute_stability,
    generate_trials,
    generate_trials_optuna,
    refine_trials_around,
    run_optimization,
    select_best,
    split_holdout,
    split_train_test,
)


def test_generate_trials_respects_max_with_sampling() -> None:
    space = OptimizationSpace(
        min_confidence=(0.6, 0.7),
        min_risk_reward=(1.2, 1.5),
        min_agreeing_providers=(1, 2),
        sl_atr_mult=(1.0, 1.5),
        tp_atr_mult=(2.0, 3.0),
        max_bars_in_trade=(24, 48),
        oversold=(30,),
        overbought=(70,),
        risk_pct_per_trade=(1.0,),
        min_atr_pct=(0.3,),
        session_preset=("eu_us",),
        max_signals_per_day=(10,),
        ema_fast=(12,),
        ema_slow=(26,),
        rsi_period=(14,),
        ema_weight=(1.0,),
        rsi_weight=(1.0,),
        ema_enabled=(1,),
        rsi_enabled=(1,),
    )
    trials = generate_trials(space, max_trials=5, seed=1)
    assert len(trials) == 5
    assert all("min_confidence" in t for t in trials)


def test_generate_trials_full_grid_when_small() -> None:
    space = OptimizationSpace(
        min_confidence=(0.6,),
        min_risk_reward=(1.2,),
        min_agreeing_providers=(1,),
        sl_atr_mult=(1.0,),
        tp_atr_mult=(2.0,),
        max_bars_in_trade=(24,),
        oversold=(30,),
        overbought=(70,),
        risk_pct_per_trade=(1.0,),
        min_atr_pct=(0.3,),
        session_preset=("eu_us",),
        max_signals_per_day=(10,),
        ema_fast=(12,),
        ema_slow=(26,),
        rsi_period=(14,),
        ema_weight=(1.0,),
        rsi_weight=(1.0,),
        ema_enabled=(1,),
        rsi_enabled=(1,),
    )
    trials = generate_trials(space, max_trials=40)
    assert len(trials) == 1
    assert trials[0]["min_confidence"] == 0.6


def test_split_train_test() -> None:
    from datetime import UTC, datetime, timedelta

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 11, tzinfo=UTC)
    train, test = split_train_test(start, end, train_ratio=0.7)
    assert train[0] == start
    assert test[1] == end
    assert train[1] == test[0]
    assert (train[1] - train[0]) == timedelta(days=7)


def test_split_holdout_reserves_tail() -> None:
    from datetime import UTC, datetime

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 11, tzinfo=UTC)
    optimization, holdout = split_holdout(start, end, holdout_ratio=0.2)
    assert optimization[0] == start
    assert holdout is not None
    assert holdout[1] == end
    assert optimization[1] == holdout[0]


def test_compute_stability() -> None:
    outcome = {
        "monthly_breakdown": [
            {"pnl": 10},
            {"pnl": -5},
            {"pnl": 20},
        ]
    }
    assert compute_stability(outcome) == pytest.approx(2 / 3)


def test_composite_score_rejects_low_trades() -> None:
    trial = TrialResult(
        trial_id="t1",
        params={},
        train_score=10,
        train_outcome={},
        test_score=50,
        test_outcome={"total_trades": 5, "return_pct": 5.0},
        stability=0.8,
    )
    assert composite_score(trial, min_trades=20) == float("-inf")


def test_select_best_returns_none_when_all_fail_guardrails() -> None:
    trial = TrialResult(
        trial_id="weak",
        params={"min_agreeing_providers": 2},
        train_score=10,
        train_outcome={},
        test_score=-20,
        test_outcome={"total_trades": 0, "return_pct": 0},
        stability=0,
    )
    assert select_best([trial], min_trades=20, min_return_pct=0.0) is None


def test_build_selection_message_mentions_agreeing_providers() -> None:
    from src.validation.optimizer import build_selection_message

    trial = TrialResult(
        trial_id="t1",
        params={"min_agreeing_providers": 2},
        train_score=0,
        train_outcome={},
        test_score=-20,
        test_outcome={"total_trades": 0, "return_pct": 0},
    )
    message = build_selection_message(
        finalists=[trial],
        min_trades=20,
        min_return_pct=0.0,
    )
    assert "2 agreeing providers" in message
    assert "max seen: 0" in message


def test_select_best_uses_composite_score() -> None:
    good = TrialResult(
        trial_id="good",
        params={},
        train_score=10,
        train_outcome={},
        test_score=40,
        test_outcome={"total_trades": 30, "return_pct": 4.0},
        stability=0.7,
    )
    flashy = TrialResult(
        trial_id="flashy",
        params={},
        train_score=20,
        train_outcome={},
        test_score=60,
        test_outcome={"total_trades": 8, "return_pct": 10.0},
        stability=0.2,
    )
    best = select_best([good, flashy], min_trades=20, min_return_pct=0.0)
    assert best is not None
    assert best.trial_id == "good"


def test_refine_trials_around_neighbors() -> None:
    space = OptimizationSpace(sl_atr_mult=(1.0, 1.5, 2.0), tp_atr_mult=(2.0, 3.0))
    base = {"sl_atr_mult": 1.5, "tp_atr_mult": 3.0}
    refined = refine_trials_around([base], space, max_refine=4)
    assert refined
    assert any(trial["sl_atr_mult"] == 1.0 for trial in refined)
    assert any(trial["sl_atr_mult"] == 2.0 for trial in refined)


def test_train_phase_uses_train_segment_not_test() -> None:
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    segments: list[str] = []

    async def fake_score(*, segment, **kwargs):
        segments.append(segment)
        return 1.0, {"total_trades": 25, "return_pct": 2.0}, [1.0], 0.0

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    space = OptimizationSpace(min_confidence=(0.6,), min_risk_reward=(1.2,))
    trials = generate_trials(space, max_trials=1)

    with (
        patch(
            "src.validation.optimizer._score_trial_windows",
            new=AsyncMock(side_effect=fake_score),
        ),
        patch(
            "src.validation.optimizer._run_trial",
            new=AsyncMock(return_value=(1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")),
        ),
        patch(
            "src.validation.optimizer.generate_trials",
            return_value=trials,
        ),
        patch("src.validation.optimizer.refine_trials_around", return_value=[]),
    ):
        import asyncio

        asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=1,
                top_k=1,
                walk_forward_windows=2,
                local_refine=False,
            )
        )

    assert segments
    assert segments[0] == "train"
    assert segments[-1] == "test"


def test_select_best_prefers_pareto_front() -> None:
    a = TrialResult(
        trial_id="a",
        params={},
        train_score=10,
        train_outcome={},
        test_score=50,
        test_outcome={
            "total_trades": 30,
            "return_pct": 3.0,
            "max_drawdown_pct": 5.0,
            "profit_factor": 1.2,
        },
        stability=0.6,
        pareto_rank=0,
    )
    b = TrialResult(
        trial_id="b",
        params={},
        train_score=10,
        train_outcome={},
        test_score=55,
        test_outcome={
            "total_trades": 30,
            "return_pct": 1.0,
            "max_drawdown_pct": 2.0,
            "profit_factor": 1.1,
        },
        stability=0.5,
        pareto_rank=1,
    )
    best = select_best([a, b], min_trades=20, min_return_pct=0.0)
    assert best is not None
    assert best.trial_id == "a"


def test_generate_trials_optuna_respects_max() -> None:
    space = OptimizationSpace(min_confidence=(0.6, 0.7), min_risk_reward=(1.2, 1.5))
    trials = generate_trials_optuna(space, max_trials=4, seed=42)
    assert len(trials) == 4
    assert all("min_confidence" in t for t in trials)


def test_holdout_evaluated_after_best_selected() -> None:
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    holdout_calls: list[tuple[datetime, datetime]] = []

    async def fake_run_trial(*, start, end, **kwargs):
        holdout_calls.append((start, end))
        return 5.0, {"total_trades": 25, "return_pct": 2.0}, "rev"

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    space = OptimizationSpace(min_confidence=(0.6,), min_risk_reward=(1.2,))
    trials = generate_trials(space, max_trials=1)

    with (
        patch(
            "src.validation.optimizer._run_trial",
            new=AsyncMock(side_effect=fake_run_trial),
        ),
        patch("src.validation.optimizer.generate_trials", return_value=trials),
        patch("src.validation.optimizer.refine_trials_around", return_value=[]),
    ):
        import asyncio

        result = asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=1,
                top_k=1,
                holdout_ratio=0.2,
                local_refine=False,
            )
        )

    assert result.holdout_start is not None
    assert result.holdout_score is not None
    assert result.holdout_valid is True
    assert holdout_calls
    assert holdout_calls[-1][0] == result.holdout_start
    assert holdout_calls[-1][1] == result.holdout_end
