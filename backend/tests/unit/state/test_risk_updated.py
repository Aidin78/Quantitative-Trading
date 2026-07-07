from __future__ import annotations

from src.state.store import InMemoryStateStore
from src.state.transitions import StateTransitionEvent
from tests.mocks.fixtures import utc_now


def test_risk_updated_increments_signals_today() -> None:
    store = InMemoryStateStore(portfolio_id="portfolio_default")
    now = utc_now()
    assert store.get_risk("portfolio_default").signals_today == 0

    snap = store.apply_transition(
        StateTransitionEvent(
            transition_id="t1",
            portfolio_id="portfolio_default",
            transition_type="risk_updated",
            payload={"signals_today": 1},
            event_time=now,
            correlation_id="c1",
        )
    )
    assert snap.risk.signals_today == 1
