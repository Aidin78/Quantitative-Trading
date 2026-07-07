from __future__ import annotations

from src.core.contracts.execution import OrderIntent
from src.execution.risk_gate import ExecutionRiskGate
from tests.mocks.fixtures import make_snapshot, make_snapshot_with_open_positions


def test_max_open_positions_rejected() -> None:
    gate = ExecutionRiskGate()
    snapshot = make_snapshot_with_open_positions(3)
    intent = OrderIntent(
        intent_id="i1",
        decision_id="d1",
        correlation_id="c1",
        symbol="BTC/USDT",
        side="BUY",
        quantity=0.1,
        limit_price=67000.0,
        stop_loss=66000.0,
        take_profit=69000.0,
        state_snapshot_id=snapshot.snapshot_id,
    )
    result = gate.check(intent, snapshot)
    assert not result.passed
    assert result.reason == "max_open_positions"


def test_sufficient_cash_passes() -> None:
    gate = ExecutionRiskGate()
    snapshot = make_snapshot()
    intent = OrderIntent(
        intent_id="i1",
        decision_id="d1",
        correlation_id="c1",
        symbol="BTC/USDT",
        side="BUY",
        quantity=0.01,
        limit_price=67000.0,
        stop_loss=66000.0,
        take_profit=69000.0,
        state_snapshot_id=snapshot.snapshot_id,
    )
    assert gate.check(intent, snapshot).passed
