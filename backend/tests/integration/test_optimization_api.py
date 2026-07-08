from __future__ import annotations

import pytest

from src.validation.optimizer import OptimizationSpace, run_optimization


@pytest.mark.asyncio
async def test_run_optimization_picks_best_on_test() -> None:
    from datetime import UTC, datetime

    result = await run_optimization(
        symbol="BTC/USDT",
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 5, tzinfo=UTC),
        source="csv",
        initial_capital=10000.0,
        train_ratio=0.7,
        max_trials=2,
        top_k=2,
        space=OptimizationSpace(
            min_confidence=(0.6,),
            min_risk_reward=(1.2, 1.5),
            min_agreeing_providers=(1,),
            sl_atr_mult=(1.0,),
            tp_atr_mult=(2.0,),
            max_bars_in_trade=(24,),
        ),
    )
    assert len(result.trials) == 2
    assert result.best is not None
    assert result.best.test_score is not None
