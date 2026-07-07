from __future__ import annotations

from src.core.contracts.event import EventEnvelope
from src.events.envelopes import ExecutionEventType


def build_trade_ledger(events: list[EventEnvelope]) -> list[dict]:
    """Build entry/exit ledger rows from POSITION_OPENED and POSITION_CLOSED events."""
    opened: dict[str, dict] = {}
    for event in events:
        if event.event_type != ExecutionEventType.POSITION_OPENED:
            continue
        position = event.payload.get("position") or {}
        position_id = event.payload.get("position_id") or position.get("position_id")
        if not position_id:
            continue
        opened[str(position_id)] = {
            "symbol": event.symbol,
            "side": position.get("side"),
            "entry_price": position.get("entry_price"),
            "stop_loss": position.get("stop_loss"),
            "take_profit": position.get("take_profit"),
            "quantity": position.get("quantity"),
            "entry_time": event.event_time.isoformat(),
        }

    trades: list[dict] = []
    for event in events:
        if event.event_type != ExecutionEventType.POSITION_CLOSED:
            continue
        payload = event.payload
        position_id = str(payload.get("position_id", ""))
        open_info = opened.get(position_id, {})
        entry_price = float(payload.get("entry_price") or open_info.get("entry_price") or 0)
        exit_price = float(payload.get("exit_price") or 0)
        quantity = float(payload.get("quantity") or open_info.get("quantity") or 0)
        pnl = float(payload.get("pnl", 0))
        notional = entry_price * quantity
        return_pct = (pnl / notional * 100) if notional > 0 else 0.0
        trades.append(
            {
                "position_id": position_id,
                "symbol": event.symbol,
                "side": payload.get("side") or open_info.get("side"),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_loss": payload.get("stop_loss") or open_info.get("stop_loss"),
                "take_profit": payload.get("take_profit") or open_info.get("take_profit"),
                "quantity": quantity,
                "exit_reason": payload.get("exit_reason"),
                "pnl": pnl,
                "return_pct": return_pct,
                "bars_held": payload.get("bars_held"),
                "entry_time": open_info.get("entry_time"),
                "exit_time": event.event_time.isoformat(),
                "win": pnl > 0,
            }
        )
    return trades
