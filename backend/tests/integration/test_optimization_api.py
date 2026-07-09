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
            macd_fast=(12,),
            macd_slow=(26,),
            macd_signal_period=(9,),
            macd_weight=(1.0,),
            macd_enabled=(1,),
            require_signal_align=(1,),
            min_histogram_slope=(0.0,),
        ),
        min_trades=0,
        holdout_ratio=0.0,
        local_refine=False,
    )
    assert len(result.trials) == 2
    assert result.best is not None
    assert result.best.test_score is not None
