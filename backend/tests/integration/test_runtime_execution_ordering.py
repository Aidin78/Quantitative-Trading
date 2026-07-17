from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pandas as pd
import pytest

from src.core.contracts.decision import (
    AggregationResult,
    Decision,
    DecisionLog,
    DecisionResult,
    StageResult,
)
from src.core.contracts.execution import FillModel
from src.core.contracts.rationale import RiskVerdict
from src.core.contracts.signal import FinalSignal
from src.core.exceptions import DataProviderError
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.execution.simulated import SimulatedExecutionEngine
from src.features.builder import DefaultFeatureBuilder
from src.features.store import InMemoryFeatureStore
from src.runtime.clocks import SimulatedClock
from src.runtime.platform_runtime import PlatformRuntime
from src.state.store import InMemoryStateStore

WARMUP = 40  # enough bars for RSI/EMA lookback before first run_cycle


class _FrameDataProvider:
    """Minimal OHLCV provider backed by an in-memory frame (end-sliced like CSV)."""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
    ) -> None:
        self._df = df.reset_index(drop=True)
        self._symbol = symbol
        self._timeframe = timeframe

    def get_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        if symbol != self._symbol or timeframe != self._timeframe:
            raise DataProviderError("unsupported symbol/timeframe")
        if end is None:
            return self._df.iloc[-limit:].reset_index(drop=True)
        end_ts = pd.Timestamp(end)
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")
        idx = int(self._df["timestamp"].searchsorted(end_ts, side="right"))
        if idx == 0:
            raise DataProviderError("No OHLCV rows on or before end time")
        start_idx = max(0, idx - limit)
        return self._df.iloc[start_idx:idx].reset_index(drop=True)


class _ScriptedDecisionEngine:
    """Queue of sides: BUY/SELL approve; None rejects. Ignores provider signals."""

    def __init__(self, sides: list[Literal["BUY", "SELL"] | None]) -> None:
        self._sides = list(sides)
        self.seen_open_counts: list[int] = []

    def process(
        self,
        signals,  # noqa: ANN001
        context,  # noqa: ANN001
        snapshot,  # noqa: ANN001
        *,
        correlation_id: str,
        event_time: datetime,
        decision_time: datetime,
        revision_id: str | None = None,
        experiment_id: str | None = None,
    ) -> Decision:
        self.seen_open_counts.append(len(snapshot.portfolio.open_positions))
        side = self._sides.pop(0) if self._sides else None
        if side is None:
            return Decision(
                decision_id=f"dec_reject_{correlation_id}",
                result=DecisionResult(value="rejected", rejection_reason="scripted_hold"),
                final_signal=None,
                decision_log=_empty_log(snapshot),
                correlation_id=correlation_id,
                event_time=event_time,
                decision_time=decision_time,
                revision_id=revision_id,
                experiment_id=experiment_id,
            )

        price = float(context.current_price)
        if side == "BUY":
            stop_loss = price * 0.95
            take_profit = price * 1.10
        else:
            stop_loss = price * 1.05
            take_profit = price * 0.90

        signal = FinalSignal(
            id=f"sig_{correlation_id}",
            symbol=context.symbol,
            side=side,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=0.9,
            risk_reward=2.0,
            timeframe=context.timeframe,
            event_time=event_time,
            decision_time=decision_time,
            contributing_providers=("scripted",),
            state_snapshot_id=snapshot.snapshot_id,
        )
        return Decision(
            decision_id=f"dec_{correlation_id}",
            result=DecisionResult(value="approved"),
            final_signal=signal,
            decision_log=_empty_log(snapshot),
            correlation_id=correlation_id,
            event_time=event_time,
            decision_time=decision_time,
            revision_id=revision_id,
            experiment_id=experiment_id,
        )


def _empty_log(snapshot) -> DecisionLog:  # noqa: ANN001
    return DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(),
        aggregation=AggregationResult(method="scripted", side="HOLD", confidence=0.0),
        risk_check=RiskVerdict(
            passed=True,
            checks=(),
            state_snapshot_id=snapshot.snapshot_id,
            risk_state_version=snapshot.risk.version,
        ),
        state_snapshot_id=snapshot.snapshot_id,
        portfolio_version=snapshot.portfolio.version,
        risk_state_version=snapshot.risk.version,
    )


def _synthetic_bars(
    *,
    n: int = 60,
    start: datetime | None = None,
    overrides: dict[int, dict[str, float]] | None = None,
) -> pd.DataFrame:
    """Build gently trending bars so RSI/ATR are defined; overrides pin specific OHLC."""
    base = start or datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    rows: list[dict] = []
    for i in range(n):
        close = 100.0 + (i % 7) * 0.4
        row = {
            "timestamp": base + timedelta(hours=i),
            "open": close - 0.2,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": 10.0 + i,
        }
        if overrides and i in overrides:
            row.update(overrides[i])
        rows.append(row)
    return pd.DataFrame(rows)


def _build_runtime(
    df: pd.DataFrame,
    sides: list[Literal["BUY", "SELL"] | None],
    *,
    fill_at: Literal["close", "next_open", "mid"] = "close",
) -> tuple[PlatformRuntime, SimulatedExecutionEngine, _ScriptedDecisionEngine, SimulatedClock]:
    start_ts = df["timestamp"].iloc[WARMUP].to_pydatetime()
    clock = SimulatedClock(
        event_time=start_ts,
        processing_time=start_ts + timedelta(seconds=2),
    )
    feature_store = InMemoryFeatureStore()
    bus = InMemoryEventBus(handlers=[EventLogHandler()])
    fill = FillModel(model_id="test", slippage_bps=0, fee_bps=0, fill_at=fill_at)
    execution = SimulatedExecutionEngine(fill, clock)
    decision_engine = _ScriptedDecisionEngine(sides)
    runtime = PlatformRuntime(
        data_provider=_FrameDataProvider(df),
        feature_builder=DefaultFeatureBuilder(store=feature_store),
        feature_store=feature_store,
        state_store=InMemoryStateStore(portfolio_id="portfolio_order"),
        providers=[],
        decision_engine=decision_engine,  # type: ignore[arg-type]
        event_bus=bus,
        clock=clock,
        portfolio_id="portfolio_order",
        mode="validation",
        execution_engine=execution,
        persist_features=False,
    )
    return runtime, execution, decision_engine, clock


async def _run_at(
    runtime: PlatformRuntime,
    clock: SimulatedClock,
    bar_time: datetime,
    *,
    correlation_id: str,
):
    clock.set_event_time(bar_time)
    clock.set_processing_time(bar_time + timedelta(seconds=2))
    return await runtime.run_cycle("BTC/USDT", "1h", correlation_id=correlation_id)


def _ts(df: pd.DataFrame, index: int) -> datetime:
    return df["timestamp"].iloc[index].to_pydatetime()


@pytest.mark.asyncio
async def test_pre_decision_stop_clears_position_before_decision() -> None:
    open_i = WARMUP
    stop_i = WARMUP + 1
    overrides = {
        stop_i: {"open": 100.0, "high": 100.5, "low": 90.0, "close": 98.0, "volume": 10.0},
    }
    df = _synthetic_bars(n=WARMUP + 2, overrides=overrides)
    runtime, _execution, decision_engine, clock = _build_runtime(df, ["BUY", None])

    open_result = await _run_at(runtime, clock, _ts(df, open_i), correlation_id="open")
    assert open_result.decision.is_approved
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 1

    stop_result = await _run_at(runtime, clock, _ts(df, stop_i), correlation_id="stop")
    assert decision_engine.seen_open_counts[-1] == 0
    assert len(stop_result.snapshot.portfolio.open_positions) == 0
    assert any(
        e.event_type == "PositionClosed" and e.payload.get("exit_reason") == "stop_loss"
        for e in stop_result.execution_events
    )


@pytest.mark.asyncio
async def test_next_open_fill_lands_on_following_cycle_pre_eval() -> None:
    entry_i = WARMUP
    fill_i = WARMUP + 1
    df = _synthetic_bars(n=WARMUP + 2)
    runtime, execution, _decision, clock = _build_runtime(df, ["BUY", None], fill_at="next_open")

    r1 = await _run_at(runtime, clock, _ts(df, entry_i), correlation_id="entry")
    assert r1.decision.is_approved
    assert len(execution._pending_entries) == 1
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 0
    assert not any(e.event_type == "FillReceived" for e in r1.execution_events)

    r2 = await _run_at(runtime, clock, _ts(df, fill_i), correlation_id="fill")
    assert len(execution._pending_entries) == 0
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 1
    fill_events = [e for e in r2.execution_events if e.event_type == "FillReceived"]
    assert len(fill_events) == 1
    assert fill_events[0].payload["fill"]["price"] == pytest.approx(
        float(df.iloc[fill_i]["open"]), abs=1e-9
    )


@pytest.mark.asyncio
async def test_signal_exit_does_not_double_increment_bars() -> None:
    open_i = WARMUP
    hold_i = WARMUP + 1
    flip_i = WARMUP + 2
    df = _synthetic_bars(n=WARMUP + 3)
    runtime, execution, _decision, clock = _build_runtime(df, ["BUY", None, "SELL"])

    await _run_at(runtime, clock, _ts(df, open_i), correlation_id="open")
    positions = runtime._state_store.get_portfolio("portfolio_order").open_positions
    assert len(positions) == 1
    pos_id = positions[0].position_id
    assert execution._position_bars.get(pos_id, 0) == 0

    await _run_at(runtime, clock, _ts(df, hold_i), correlation_id="hold")
    assert execution._position_bars.get(pos_id) == 1

    eval_flags: list[bool] = []
    original = execution.evaluate_bar

    async def tracked_evaluate_bar(*args, **kwargs):  # noqa: ANN002, ANN003
        eval_flags.append(bool(kwargs.get("increment_bars", True)))
        return await original(*args, **kwargs)

    execution.evaluate_bar = tracked_evaluate_bar  # type: ignore[method-assign]

    flip = await _run_at(runtime, clock, _ts(df, flip_i), correlation_id="flip")
    assert eval_flags == [True, False]
    assert any(
        e.event_type == "PositionClosed" and e.payload.get("exit_reason") == "signal"
        for e in flip.execution_events
    )
    assert execution._position_bars.get(pos_id, 2) <= 2


@pytest.mark.asyncio
async def test_multi_bar_open_hold_then_take_profit() -> None:
    open_i = WARMUP
    hold_i = WARMUP + 1
    tp_i = WARMUP + 2
    overrides = {
        tp_i: {"open": 100.0, "high": 120.0, "low": 99.5, "close": 115.0, "volume": 10.0},
    }
    df = _synthetic_bars(n=WARMUP + 3, overrides=overrides)
    runtime, _execution, _decision, clock = _build_runtime(df, ["BUY", None, None])

    await _run_at(runtime, clock, _ts(df, open_i), correlation_id="open")
    await _run_at(runtime, clock, _ts(df, hold_i), correlation_id="hold")
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 1

    tp = await _run_at(runtime, clock, _ts(df, tp_i), correlation_id="tp")
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 0
    assert any(
        e.event_type == "PositionClosed" and e.payload.get("exit_reason") == "take_profit"
        for e in tp.execution_events
    )


@pytest.mark.asyncio
async def test_harness_style_liquidation_closes_at_last_close() -> None:
    open_i = WARMUP
    df = _synthetic_bars(n=WARMUP + 1)
    runtime, execution, _decision, clock = _build_runtime(df, ["BUY"])

    await _run_at(runtime, clock, _ts(df, open_i), correlation_id="open")
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 1

    last_time = _ts(df, open_i)
    last_row = df.iloc[open_i]
    bar = {
        "open": float(last_row["open"]),
        "high": float(last_row["high"]),
        "low": float(last_row["low"]),
        "close": float(last_row["close"]),
        "volume": float(last_row["volume"]),
    }
    snapshot = runtime._state_store.snapshot("portfolio_order", correlation_id="liquidate")
    result = await execution.liquidate_open_positions(
        bar,
        snapshot,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="liquidate",
        event_time=last_time,
        processing_time=last_time + timedelta(seconds=2),
    )
    for transition in result.transitions:
        runtime._state_store.apply_transition(transition)

    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 0
    close = next(e for e in result.events if e.event_type == "PositionClosed")
    assert close.payload["exit_reason"] == "end_of_run"
    assert close.payload["exit_price"] == float(last_row["close"])


@pytest.mark.asyncio
async def test_cycle_result_snapshot_is_decision_time_not_post_execute() -> None:
    open_i = WARMUP
    df = _synthetic_bars(n=WARMUP + 1)
    runtime, _execution, _decision, clock = _build_runtime(df, ["BUY"])

    result = await _run_at(runtime, clock, _ts(df, open_i), correlation_id="open")
    assert result.decision.is_approved
    assert len(result.snapshot.portfolio.open_positions) == 0
    assert len(runtime._state_store.get_portfolio("portfolio_order").open_positions) == 1
