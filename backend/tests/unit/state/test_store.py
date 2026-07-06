from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.state.store import InMemoryStateStore
from src.state.transitions import StateTransitionEvent


def test_snapshot_creates_immutable_state() -> None:
    store = InMemoryStateStore(portfolio_id="p1")
    snap = store.snapshot("p1", correlation_id="cycle_001")
    assert snap.portfolio.portfolio_id == "p1"
    assert snap.risk.portfolio_id == "p1"
    assert snap.correlation_id == "cycle_001"
    assert snap.snapshot_id.startswith("snap_")


def test_apply_transition_not_implemented() -> None:
    store = InMemoryStateStore(portfolio_id="p1")
    event = StateTransitionEvent(
        transition_id="tr_1",
        portfolio_id="p1",
        transition_type="position_opened",
        event_time=datetime.now(UTC),
        correlation_id="cycle_001",
    )
    with pytest.raises(NotImplementedError):
        store.apply_transition(event)
