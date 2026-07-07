from __future__ import annotations

from src.core.contracts.state import PositionState
from src.state.store import InMemoryStateStore
from src.state.transitions import StateTransitionEvent
from tests.mocks.fixtures import utc_now


def test_position_opened_reduces_cash() -> None:
    store = InMemoryStateStore(initial_cash=10000.0)
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
    event = StateTransitionEvent(
        transition_id="t1",
        portfolio_id="portfolio_default",
        transition_type="position_opened",
        payload={"position": position.model_dump(mode="json"), "cost": 6700.0},
        event_time=now,
        correlation_id="c1",
    )
    snap = store.apply_transition(event)
    assert len(snap.portfolio.open_positions) == 1
    assert snap.portfolio.cash == 3300.0
    assert snap.portfolio.version == 2


def test_position_closed_updates_pnl() -> None:
    store = InMemoryStateStore(initial_cash=10000.0)
    now = utc_now()
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
    snap = store.apply_transition(
        StateTransitionEvent(
            transition_id="t2",
            portfolio_id="portfolio_default",
            transition_type="position_closed",
            payload={"position_id": "pos_1", "pnl": 200.0, "exit_reason": "take_profit"},
            event_time=now,
            correlation_id="c2",
        )
    )
    assert snap.portfolio.open_positions == ()
    assert snap.portfolio.realized_pnl == 200.0
    assert snap.portfolio.equity == 10200.0
