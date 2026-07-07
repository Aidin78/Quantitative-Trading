from __future__ import annotations

from src.core.contracts.event import EventFamily
from src.events.envelopes import ExecutionEventType, build_envelope
from src.validation.trades import build_trade_ledger
from tests.mocks.fixtures import utc_now


def test_build_trade_ledger_pairs_open_and_close() -> None:
    now = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_OPENED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "position_id": "pos_1",
                "position": {
                    "position_id": "pos_1",
                    "symbol": "BTC/USDT",
                    "side": "LONG",
                    "quantity": 0.1,
                    "entry_price": 67000.0,
                    "stop_loss": 66000.0,
                    "take_profit": 69000.0,
                },
            },
        ),
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "position_id": "pos_1",
                "exit_reason": "take_profit",
                "exit_price": 69000.0,
                "entry_price": 67000.0,
                "side": "LONG",
                "quantity": 0.1,
                "pnl": 200.0,
                "bars_held": 3,
            },
        ),
    ]
    trades = build_trade_ledger(events)
    assert len(trades) == 1
    assert trades[0]["entry_price"] == 67000.0
    assert trades[0]["exit_price"] == 69000.0
    assert trades[0]["exit_reason"] == "take_profit"
    assert trades[0]["win"] is True
