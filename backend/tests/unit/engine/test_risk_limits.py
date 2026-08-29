from __future__ import annotations

import pytest

from src.core.contracts.state import PositionState
from src.state.store import InMemoryStateStore
from src.state.transitions import StateTransitionEvent
from tests.mocks.fixtures import make_context, make_snapshot, make_snapshot_with_open_positions
from tests.mocks.mock_signals import consensus_buy_signals, make_signal


def test_max_daily_drawdown_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(drawdown_pct=6.0),
        correlation_id="cycle_max_daily_drawdown",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "daily_drawdown"


def test_below_max_daily_drawdown_not_rejected_on_this_check(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(drawdown_pct=4.0),
        correlation_id="cycle_below_max_daily_drawdown",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert decision.result.rejection_reason != "daily_drawdown"


def test_real_state_store_loss_produces_working_daily_drawdown_circuit_breaker(
    engine, times: dict
) -> None:
    """End-to-end proof the circuit breaker is real, not a mock-fixture artifact.

    Exercises the actual StateStore transition path (position open -> position
    close with a loss) rather than a hand-built RiskState, then feeds the
    resulting snapshot into RiskManager.evaluate via the real DecisionEngine.
    """
    store = InMemoryStateStore(initial_cash=10000.0)
    now = times["event_time"]

    position = PositionState(
        position_id="pos_1",
        symbol="BTC/USDT",
        side="LONG",
        quantity=0.1,
        entry_price=67000.0,
        entry_time=now,
    )
    store.apply_transition(
        StateTransitionEvent(
            transition_id="t1",
            portfolio_id="portfolio_default",
            transition_type="position_opened",
            payload={"position": position.model_dump(mode="json"), "cost": 6700.0},
            event_time=now,
            correlation_id="c1",
        )
    )
    # Loss of 600 on 10000 starting equity -> 6% daily drawdown, above the 5% default limit.
    snapshot = store.apply_transition(
        StateTransitionEvent(
            transition_id="t2",
            portfolio_id="portfolio_default",
            transition_type="position_closed",
            payload={"position_id": "pos_1", "pnl": -600.0, "exit_reason": "stop_loss"},
            event_time=now,
            correlation_id="c2",
        )
    )
    assert snapshot.risk.daily_drawdown_pct == pytest.approx(6.0)

    decision = engine.process(
        consensus_buy_signals(now),
        make_context(),
        snapshot,
        correlation_id="cycle_real_daily_drawdown",
        event_time=now,
        decision_time=now,
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "daily_drawdown"


def test_max_open_positions_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot_with_open_positions(3),
        correlation_id="cycle_max_positions",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_open_positions"


def test_opposing_exit_not_blocked_by_max_open_positions(engine, times: dict) -> None:
    """A SELL that closes an open LONG must not be rejected at the position cap."""
    decision = engine.process(
        [
            make_signal("ema_crossover", "SELL", 0.78, event_time=times["event_time"]),
            make_signal("rsi_divergence", "SELL", 0.72, event_time=times["event_time"]),
        ],
        make_context(),
        make_snapshot_with_open_positions(3),  # 3 LONGs, cap 3
        correlation_id="cycle_opposing_exit",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert decision.result.rejection_reason != "max_open_positions"


def test_max_exposure_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(exposure_pct=60.0),
        correlation_id="cycle_max_exposure",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_exposure"


def test_max_consecutive_losses_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(consecutive_losses=5, max_consecutive_losses=5),
        correlation_id="cycle_max_consecutive_losses",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_consecutive_losses"


def test_below_max_consecutive_losses_not_rejected_on_this_check(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(consecutive_losses=4, max_consecutive_losses=5),
        correlation_id="cycle_below_max_consecutive_losses",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert decision.result.rejection_reason != "max_consecutive_losses"
