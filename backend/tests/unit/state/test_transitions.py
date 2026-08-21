from __future__ import annotations

import pytest

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


def test_position_closed_with_loss_updates_daily_drawdown_pct() -> None:
    store = InMemoryStateStore(initial_cash=10000.0)
    now = utc_now()
    assert store.get_risk("portfolio_default").daily_start_equity == 10000.0

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
            payload={"position_id": "pos_1", "pnl": -500.0, "exit_reason": "stop_loss"},
            event_time=now,
            correlation_id="c2",
        )
    )
    assert snap.portfolio.equity == 9500.0
    assert snap.risk.daily_drawdown_pct == pytest.approx(5.0)


def test_mark_to_market_updates_equity_and_drawdown_for_open_position() -> None:
    store = InMemoryStateStore(initial_cash=10000.0)
    now = utc_now()
    assert store.get_risk("portfolio_default").daily_start_equity == 10000.0

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

    # Price drops sharply against the open long — equity/drawdown must move
    # even though nothing has been closed/realized yet.
    snap = store.apply_transition(
        StateTransitionEvent(
            transition_id="t2",
            portfolio_id="portfolio_default",
            transition_type="mark_to_market",
            payload={"prices": {"BTC/USDT": 62000.0}},
            event_time=now,
            correlation_id="c2",
        )
    )

    assert snap.portfolio.equity == pytest.approx(9500.0)
    assert snap.portfolio.open_positions[0].unrealized_pnl == pytest.approx(-500.0)
    assert snap.risk.daily_drawdown_pct == pytest.approx(5.0)
    # Cash and realized_pnl are untouched by mark-to-market.
    assert snap.portfolio.cash == 3300.0
    assert snap.portfolio.realized_pnl == 0.0


def test_mark_to_market_recovers_when_price_moves_back_in_favor() -> None:
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
    store.apply_transition(
        StateTransitionEvent(
            transition_id="t2",
            portfolio_id="portfolio_default",
            transition_type="mark_to_market",
            payload={"prices": {"BTC/USDT": 62000.0}},
            event_time=now,
            correlation_id="c2",
        )
    )
    snap = store.apply_transition(
        StateTransitionEvent(
            transition_id="t3",
            portfolio_id="portfolio_default",
            transition_type="mark_to_market",
            payload={"prices": {"BTC/USDT": 67000.0}},
            event_time=now,
            correlation_id="c3",
        )
    )
    assert snap.portfolio.equity == pytest.approx(10000.0)
    assert snap.risk.daily_drawdown_pct == 0.0


def test_mark_to_market_no_open_positions_is_noop() -> None:
    store = InMemoryStateStore(initial_cash=10000.0)
    now = utc_now()
    snap = store.apply_transition(
        StateTransitionEvent(
            transition_id="t1",
            portfolio_id="portfolio_default",
            transition_type="mark_to_market",
            payload={"prices": {"BTC/USDT": 62000.0}},
            event_time=now,
            correlation_id="c1",
        )
    )
    assert snap.portfolio.equity == 10000.0
    assert snap.risk.daily_drawdown_pct == 0.0


def test_position_closed_with_profit_keeps_drawdown_zero() -> None:
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
    assert snap.risk.daily_drawdown_pct == 0.0
