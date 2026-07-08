from __future__ import annotations

import pytest

from src.providers.base import ProviderConfig
from src.providers.ema_crossover import EmaCrossoverProvider
from src.validation.optimizer import (
    OptimizationSpace,
    compute_stability,
    generate_trials,
    split_train_test,
)
from tests.mocks.fixtures import make_context


def test_generate_trials_respects_max_with_sampling() -> None:
    space = OptimizationSpace(
        min_confidence=(0.6, 0.7),
        min_risk_reward=(1.2, 1.5),
        min_agreeing_providers=(1, 2),
        sl_atr_mult=(1.0, 1.5),
        tp_atr_mult=(2.0, 3.0),
        max_bars_in_trade=(24, 48),
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


def test_compute_stability() -> None:
    outcome = {
        "monthly_breakdown": [
            {"pnl": 10},
            {"pnl": -5},
            {"pnl": 20},
        ]
    }
    assert compute_stability(outcome) == pytest.approx(2 / 3)


def test_atr_stops_use_provider_params() -> None:
    provider = EmaCrossoverProvider(
        ProviderConfig(
            provider_id="ema_crossover",
            params={"sl_atr_mult": 2.0, "tp_atr_mult": 4.0},
        )
    )
    context = make_context(current_price=100.0, atr_pct=1.0)
    sl, tp = provider._atr_stops(context, "BUY")
    assert sl == pytest.approx(98.0)
    assert tp == pytest.approx(104.0)
