from __future__ import annotations

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
from src.execution.simulated import SimulatedExecutionEngine
from src.runtime.clocks import SimulatedClock
from tests.mocks.fixtures import make_snapshot, utc_now


def _approved_decision(snapshot) -> Decision:
    now = utc_now()
    signal = FinalSignal(
        id="sig_1",
        symbol="BTC/USDT",
        side="BUY",
        entry_price=67000.0,
        stop_loss=60000.0,
        take_profit=69000.0,
        confidence=0.8,
        risk_reward=2.0,
        timeframe="1h",
        event_time=now,
        decision_time=now,
        contributing_providers=("ema_crossover", "rsi_divergence"),
        state_snapshot_id=snapshot.snapshot_id,
    )
    log = DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(),
        aggregation=AggregationResult(method="majority", side="BUY", confidence=0.8),
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
    return Decision(
        decision_id="dec_test_1",
        result=DecisionResult(value="approved"),
        final_signal=signal,
        decision_log=log,
        correlation_id="cycle_test",
        event_time=now,
        decision_time=now,
    )


@pytest.fixture
def engine() -> SimulatedExecutionEngine:
    fill = FillModel(model_id="test", slippage_bps=10, fee_bps=10, fill_at="close")
    clock = SimulatedClock(event_time=utc_now())
    return SimulatedExecutionEngine(fill, clock)


@pytest.mark.asyncio
async def test_execute_creates_order_intent_and_position(engine: SimulatedExecutionEngine) -> None:
    snapshot = make_snapshot(exposure_pct=0.0)
    bar = {"open": 66900, "high": 67100, "low": 66800, "close": 67000, "volume": 100}
    decision = _approved_decision(snapshot)
    result = await engine.execute(
        decision,
        snapshot,
        bar,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_test",
        processing_time=utc_now(),
    )
    types = [e.event_type for e in result.events]
    assert "OrderIntentCreated" in types
    assert "FillReceived" in types
    assert "PositionOpened" in types
    assert len(result.transitions) == 1


@pytest.mark.asyncio
async def test_fill_price_includes_slippage(engine: SimulatedExecutionEngine) -> None:
    snapshot = make_snapshot(exposure_pct=0.0)
    bar = {"open": 100, "high": 110, "low": 90, "close": 100, "volume": 1}
    decision = _approved_decision(snapshot)
    result = await engine.execute(
        decision,
        snapshot,
        bar,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_test",
        processing_time=utc_now(),
    )
    fill_event = next(e for e in result.events if e.event_type == "FillReceived")
    fill_price = fill_event.payload["fill"]["price"]
    assert fill_price > 100.0


@pytest.mark.asyncio
async def test_evaluate_bar_stop_loss_closes_long(engine: SimulatedExecutionEngine) -> None:
    from src.core.contracts.state import PositionState

    now = utc_now()
    position = PositionState(
        position_id="pos_1",
        symbol="BTC/USDT",
        side="LONG",
        quantity=0.1,
        entry_price=67000.0,
        entry_time=now,
        stop_loss=66000.0,
        take_profit=69000.0,
    )
    snapshot = make_snapshot(exposure_pct=0.0)
    portfolio = snapshot.portfolio.model_copy(update={"open_positions": (position,)})
    snap = snapshot.model_copy(update={"portfolio": portfolio})

    engine._position_bars["pos_1"] = 0
    bar = {"open": 66500, "high": 66600, "low": 65500, "close": 65800, "volume": 100}
    result = await engine.evaluate_bar(
        bar,
        snap,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_exit",
        event_time=now,
        processing_time=now,
    )
    assert any(e.event_type == "PositionClosed" for e in result.events)
    close = next(e for e in result.events if e.event_type == "PositionClosed")
    assert close.payload["exit_reason"] == "stop_loss"


@pytest.mark.asyncio
async def test_evaluate_bar_signal_exit_closes_long(engine: SimulatedExecutionEngine) -> None:
    from src.core.contracts.state import PositionState

    now = utc_now()
    position = PositionState(
        position_id="pos_signal",
        symbol="BTC/USDT",
        side="LONG",
        quantity=0.1,
        entry_price=67000.0,
        entry_time=now,
    )
    snapshot = make_snapshot(exposure_pct=0.0)
    portfolio = snapshot.portfolio.model_copy(update={"open_positions": (position,)})
    snap = snapshot.model_copy(update={"portfolio": portfolio})
    engine._position_bars["pos_signal"] = 1

    bar = {"open": 67100, "high": 67200, "low": 67000, "close": 67150, "volume": 100}
    result = await engine.evaluate_bar(
        bar,
        snap,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_signal",
        event_time=now,
        processing_time=now,
        approved_side="SELL",
        increment_bars=False,
    )
    close = next(e for e in result.events if e.event_type == "PositionClosed")
    assert close.payload["exit_reason"] == "signal"


@pytest.mark.asyncio
async def test_next_open_defers_fill_to_next_bar() -> None:
    fill = FillModel(model_id="test", slippage_bps=0, fee_bps=0, fill_at="next_open")
    clock = SimulatedClock(event_time=utc_now())
    engine = SimulatedExecutionEngine(fill, clock)
    snapshot = make_snapshot(exposure_pct=0.0)
    bar1 = {"open": 66800, "high": 67100, "low": 66700, "close": 67000, "volume": 100}
    decision = _approved_decision(snapshot)

    result1 = await engine.execute(
        decision,
        snapshot,
        bar1,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_next",
        processing_time=utc_now(),
    )
    assert not any(e.event_type == "FillReceived" for e in result1.events)
    assert len(engine._pending_entries) == 1

    bar2 = {"open": 66950, "high": 67200, "low": 66900, "close": 67100, "volume": 100}
    result2 = await engine.evaluate_bar(
        bar2,
        snapshot,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_next_2",
        event_time=utc_now(),
        processing_time=utc_now(),
    )
    fill_event = next(e for e in result2.events if e.event_type == "FillReceived")
    assert fill_event.payload["fill"]["price"] == 66950.0


@pytest.mark.asyncio
async def test_execution_failed_on_zero_quantity() -> None:
    fill = FillModel(model_id="test", slippage_bps=0, fee_bps=0, fill_at="close")
    engine = SimulatedExecutionEngine(fill, SimulatedClock(event_time=utc_now()))
    snapshot = make_snapshot(exposure_pct=0.0)
    decision = _approved_decision(snapshot)
    decision = decision.model_copy(
        update={
            "final_signal": decision.final_signal.model_copy(
                update={"entry_price": 67000.0, "stop_loss": 67000.0}
            )
        }
    )
    result = await engine.execute(
        decision,
        snapshot,
        {"open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_fail",
        processing_time=utc_now(),
    )
    assert any(e.event_type == "ExecutionFailed" for e in result.events)


def test_position_size_capped_by_available_cash(engine: SimulatedExecutionEngine) -> None:
    snapshot = make_snapshot(exposure_pct=0.0)
    qty = engine._position_size(snapshot, entry=100_000.0, stop_loss=99_500.0)
    max_affordable = snapshot.portfolio.cash / 100_000.0
    assert qty <= max_affordable + 1e-12
    assert qty > 0


@pytest.mark.asyncio
async def test_tight_stop_btc_passes_risk_gate(engine: SimulatedExecutionEngine) -> None:
    snapshot = make_snapshot(exposure_pct=0.0)
    decision = _approved_decision(snapshot)
    decision = decision.model_copy(
        update={
            "final_signal": decision.final_signal.model_copy(
                update={
                    "entry_price": 100_000.0,
                    "stop_loss": 99_500.0,
                    "take_profit": 103_000.0,
                }
            )
        }
    )
    bar = {"open": 99900, "high": 100100, "low": 99800, "close": 100_000, "volume": 100}
    result = await engine.execute(
        decision,
        snapshot,
        bar,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="cycle_tight_stop",
        processing_time=utc_now(),
    )
    assert not any(e.event_type == "OrderRejected" for e in result.events)
    assert any(e.event_type == "PositionOpened" for e in result.events)


@pytest.mark.asyncio
async def test_liquidate_open_positions_end_of_run(engine: SimulatedExecutionEngine) -> None:
    from src.core.contracts.state import PositionState

    now = utc_now()
    position = PositionState(
        position_id="pos_eor",
        symbol="BTC/USDT",
        side="LONG",
        quantity=0.01,
        entry_price=67000.0,
        entry_time=now,
        stop_loss=66000.0,
        take_profit=69000.0,
    )
    snapshot = make_snapshot(exposure_pct=0.0)
    portfolio = snapshot.portfolio.model_copy(update={"open_positions": (position,)})
    snap = snapshot.model_copy(update={"portfolio": portfolio})
    engine._position_bars["pos_eor"] = 5
    engine._position_orders["pos_eor"] = "ord_eor"

    bar = {"open": 67100, "high": 67200, "low": 67000, "close": 67150, "volume": 100}
    result = await engine.liquidate_open_positions(
        bar,
        snap,
        symbol="BTC/USDT",
        timeframe="1h",
        correlation_id="liquidate_test",
        event_time=now,
        processing_time=now,
    )
    close = next(e for e in result.events if e.event_type == "PositionClosed")
    assert close.payload["exit_reason"] == "end_of_run"
    assert close.payload["exit_price"] == 67150.0
