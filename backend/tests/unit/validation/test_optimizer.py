from __future__ import annotations

import pytest

from src.validation.optimizer import (
    OptimizationSpace,
    TrialResult,
    composite_score,
    compute_stability,
    generate_trials,
    generate_trials_optuna,
    has_any_provider_enabled,
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
            "src.validation.optimization_runner._score_trial_windows",
            new=AsyncMock(side_effect=fake_score),
        ),
        patch(
            "src.validation.optimization_runner._run_trial",
            new=AsyncMock(return_value=(1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")),
        ),
        patch(
            "src.validation.optimization_runner.generate_trials",
            return_value=trials,
        ),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
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


def _discovery_space() -> OptimizationSpace:
    """Minimal grid: only provider flags vary (avoids huge cartesian product)."""
    return OptimizationSpace(
        min_confidence=(0.65,),
        min_risk_reward=(1.2,),
        min_agreeing_providers=(1, 2, 3),
        sl_atr_mult=(1.5,),
        tp_atr_mult=(3.0,),
        max_bars_in_trade=(24,),
        oversold=(30.0,),
        overbought=(70.0,),
        risk_pct_per_trade=(1.0,),
        min_atr_pct=(0.3,),
        session_preset=("all",),
        max_signals_per_day=(10,),
        ema_fast=(12,),
        ema_slow=(26,),
        rsi_period=(14,),
        ema_weight=(1.0,),
        rsi_weight=(1.0,),
        ema_enabled=(0, 1),
        rsi_enabled=(0, 1),
        macd_fast=(12,),
        macd_slow=(26,),
        macd_signal_period=(9,),
        macd_weight=(1.0,),
        macd_enabled=(0, 1),
        require_signal_align=(1,),
        min_histogram_slope=(0.0,),
        adx_period=(14,),
        adx_weight=(1.0,),
        adx_enabled=(0, 1),
        min_adx=(25.0,),
        min_di_spread=(5.0,),
        adx_require_trend=(0,),
        bb_period=(20,),
        bb_std=(2.0,),
        bb_weight=(1.0,),
        bb_enabled=(0, 1),
        bb_avoid_high_vol=(1,),
        bb_max_adx=(0.0,),
        st_period=(10,),
        st_multiplier=(3.0,),
        st_weight=(1.0,),
        st_enabled=(0, 1),
        st_require_trend=(0,),
        vol_period=(20,),
        vol_weight=(1.0,),
        vol_enabled=(0, 1),
        min_cmf=(0.05,),
        min_volume_ratio=(1.2,),
        vol_require_price_align=(1,),
        ms_pivot_bars=(5,),
        ms_weight=(1.0,),
        ms_enabled=(0, 1),
        ms_require_bos=(1,),
        ms_require_trend=(0,),
    )


def test_has_any_provider_enabled() -> None:
    all_off = {key: 0 for key in ("ema_enabled", "rsi_enabled", "macd_enabled")}
    assert has_any_provider_enabled(all_off) is False
    all_off["ema_enabled"] = 1
    assert has_any_provider_enabled(all_off) is True


def test_generate_trials_rejects_all_disabled_combos() -> None:
    space = _discovery_space()
    trials = generate_trials(space, max_trials=10, seed=1)
    assert len(trials) == 10
    assert all(has_any_provider_enabled(trial) for trial in trials)


def test_generate_trials_raises_when_only_disabled_combos() -> None:
    space = OptimizationSpace(
        ema_enabled=(0,),
        rsi_enabled=(0,),
        macd_enabled=(0,),
        adx_enabled=(0,),
        bb_enabled=(0,),
        st_enabled=(0,),
        vol_enabled=(0,),
        ms_enabled=(0,),
    )
    with pytest.raises(ValueError, match="no valid provider"):
        generate_trials(space, max_trials=5)


def test_generate_trials_optuna_skips_all_disabled() -> None:
    space = _discovery_space()
    trials = generate_trials_optuna(space, max_trials=8, seed=7)
    assert len(trials) == 8
    assert all(has_any_provider_enabled(trial) for trial in trials)


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
            "src.validation.optimization_runner._run_trial",
            new=AsyncMock(side_effect=fake_run_trial),
        ),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
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


def test_aggregate_fold_outcomes_sums_trades_and_means_returns() -> None:
    from src.validation.optimizer import _aggregate_fold_outcomes

    aggregated = _aggregate_fold_outcomes(
        [
            {"total_trades": 10, "return_pct": 2.0, "sharpe_ratio": 1.0},
            {"total_trades": 20, "return_pct": 4.0, "sharpe_ratio": 3.0},
        ]
    )
    assert aggregated["total_trades"] == 30
    assert aggregated["return_pct"] == pytest.approx(3.0)
    assert aggregated["sharpe_ratio"] == pytest.approx(2.0)


def test_select_best_uses_aggregated_trades_from_folds() -> None:
    # Two folds with 12 trades each → aggregated 24 meets min_trades=20.
    trial = TrialResult(
        trial_id="agg",
        params={},
        train_score=10,
        train_outcome={},
        test_score=40,
        test_outcome={"total_trades": 24, "return_pct": 3.0},
        stability=0.5,
        fold_scores=[40.0, 40.0],
        fold_std=0.0,
    )
    best = select_best([trial], min_trades=20, min_return_pct=0.0)
    assert best is not None
    assert best.trial_id == "agg"


def test_exchange_prefetch_covers_full_range_including_holdout() -> None:
    from datetime import UTC, datetime
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    download_calls: list[tuple[datetime, datetime]] = []

    async def fake_download(*, start, end, **kwargs):
        download_calls.append((start, end))
        return Path("cache.csv")

    async def fake_run_trial(**kwargs):
        return 5.0, {"total_trades": 25, "return_pct": 2.0}, "rev"

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    space = OptimizationSpace(min_confidence=(0.6,), min_risk_reward=(1.2,))
    trials = generate_trials(space, max_trials=1)

    with (
        patch(
            "src.validation.optimization_runner.get_or_download_csv",
            new=AsyncMock(side_effect=fake_download),
        ),
        patch(
            "src.validation.optimization_runner.get_settings",
            return_value=type("S", (), {"exchange_id": "binance"})(),
        ),
        patch(
            "src.validation.optimization_runner._run_trial",
            new=AsyncMock(side_effect=fake_run_trial),
        ),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
    ):
        import asyncio

        asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="exchange",
                max_trials=1,
                top_k=1,
                holdout_ratio=0.2,
                local_refine=False,
            )
        )

    assert download_calls == [(start, end)]


def test_holdout_failure_sets_fallback_and_invalid_best() -> None:
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    (_, _), holdout = split_holdout(start, end, holdout_ratio=0.2)
    assert holdout is not None
    holdout_start, _holdout_end = holdout

    async def fake_run_trial(*, start, end, **kwargs):
        if start >= holdout_start:
            return 1.0, {"total_trades": 1, "return_pct": -1.0}, "rev"
        return 5.0, {"total_trades": 25, "return_pct": 2.0}, "rev"

    space = OptimizationSpace(min_confidence=(0.6,), min_risk_reward=(1.2,))
    trials = generate_trials(space, max_trials=1)

    with (
        patch(
            "src.validation.optimization_runner._run_trial",
            new=AsyncMock(side_effect=fake_run_trial),
        ),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
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
                min_trades=20,
                min_trades_holdout=10,
                local_refine=False,
            )
        )

    assert result.best is not None
    assert result.best_valid is False
    assert result.holdout_valid is False
    assert result.fallback_trial is not None
    assert result.selection_message is not None
    assert "Holdout check failed" in result.selection_message
    assert "use_fallback=true" in result.selection_message


def test_walk_forward_result_labels_span_all_folds() -> None:
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    async def fake_score(**kwargs):
        return 1.0, {"total_trades": 25, "return_pct": 2.0}, [1.0, 1.0], 0.0

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    space = OptimizationSpace(min_confidence=(0.6,), min_risk_reward=(1.2,))
    trials = generate_trials(space, max_trials=1)

    with (
        patch(
            "src.validation.optimization_runner._score_trial_windows",
            new=AsyncMock(side_effect=fake_score),
        ),
        patch(
            "src.validation.optimization_runner._run_trial",
            new=AsyncMock(return_value=(1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")),
        ),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
    ):
        import asyncio

        from src.validation.walk_forward import build_anchored_walk_forward_windows

        result = asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=1,
                top_k=1,
                walk_forward_windows=3,
                walk_forward_mode="anchored",
                holdout_ratio=0.0,
                local_refine=False,
            )
        )
        windows = build_anchored_walk_forward_windows(start, end, windows=3, train_ratio=0.7)

    assert result.train_start == windows[0].train_start
    assert result.train_end == max(w.train_end for w in windows)
    assert result.test_start == min(w.test_start for w in windows)
    assert result.test_end == windows[-1].test_end


def test_train_phase_default_is_sequential() -> None:
    """max_parallel_trials=1 keeps at most one train trial in flight."""
    import asyncio
    from datetime import UTC, datetime
    from unittest.mock import patch

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    (opt_start, opt_end), _ = split_holdout(start, end, holdout_ratio=0.0)
    (train_start, train_end), _ = split_train_test(opt_start, opt_end, train_ratio=0.7)

    active = 0
    max_active = 0
    train_calls = 0

    async def fake_run_trial(*, start, end, **kwargs):
        nonlocal active, max_active, train_calls
        if start == train_start and end == train_end:
            train_calls += 1
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return (float(train_calls), {"total_trades": 25, "return_pct": 2.0}, "rev")
        return (1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")

    space = OptimizationSpace(min_confidence=(0.6, 0.7), min_risk_reward=(1.2, 1.5))
    trials = generate_trials(space, max_trials=3, seed=1)

    with (
        patch("src.validation.optimization_runner._run_trial", new=fake_run_trial),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
    ):
        result = asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=3,
                top_k=1,
                holdout_ratio=0.0,
                local_refine=False,
                max_parallel_trials=1,
            )
        )

    assert train_calls == 3
    assert max_active == 1
    assert len(result.trials) >= 1


def test_train_phase_parallel_trials_overlap() -> None:
    """max_parallel_trials=2 allows concurrent train _run_trial calls."""
    import asyncio
    from datetime import UTC, datetime
    from unittest.mock import patch

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    (opt_start, opt_end), _ = split_holdout(start, end, holdout_ratio=0.0)
    (train_start, train_end), _ = split_train_test(opt_start, opt_end, train_ratio=0.7)

    active = 0
    max_active = 0
    train_calls = 0

    async def fake_run_trial(*, start, end, **kwargs):
        nonlocal active, max_active, train_calls
        if start == train_start and end == train_end:
            train_calls += 1
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            return (float(train_calls), {"total_trades": 25, "return_pct": 2.0}, "rev")
        return (1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")

    space = OptimizationSpace(min_confidence=(0.6, 0.7), min_risk_reward=(1.2, 1.5))
    trials = generate_trials(space, max_trials=4, seed=1)

    with (
        patch("src.validation.optimization_runner._run_trial", new=fake_run_trial),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
    ):
        result = asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=4,
                top_k=2,
                holdout_ratio=0.0,
                local_refine=False,
                max_parallel_trials=2,
            )
        )

    assert train_calls == 4
    assert max_active >= 2
    assert len(result.trials) >= 1


def test_train_phase_cancel_cancels_sibling_tasks() -> None:
    """A failing train trial cancels in-flight siblings and re-raises."""
    import asyncio
    from datetime import UTC, datetime
    from unittest.mock import patch

    started = 0
    finished = 0

    async def fake_run_trial(**kwargs):
        nonlocal started, finished
        started += 1
        my_id = started
        try:
            if my_id == 1:
                await asyncio.sleep(0.02)
                raise asyncio.CancelledError()
            await asyncio.sleep(1.0)
            finished += 1
            return (1.0, {"total_trades": 25, "return_pct": 2.0}, "rev")
        except asyncio.CancelledError:
            raise

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    space = OptimizationSpace(min_confidence=(0.6, 0.7), min_risk_reward=(1.2, 1.5))
    trials = generate_trials(space, max_trials=3, seed=1)

    with (
        patch("src.validation.optimization_runner._run_trial", new=fake_run_trial),
        patch("src.validation.optimization_runner.generate_trials", return_value=trials),
        patch("src.validation.optimization_runner.refine_trials_around", return_value=[]),
        pytest.raises(asyncio.CancelledError),
    ):
        asyncio.run(
            run_optimization(
                symbol="BTC/USDT",
                timeframe="1h",
                start=start,
                end=end,
                source="csv",
                max_trials=3,
                top_k=1,
                holdout_ratio=0.0,
                local_refine=False,
                max_parallel_trials=2,
            )
        )

    assert started >= 2
    assert finished == 0
