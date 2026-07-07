from __future__ import annotations

from src.api.websocket.decisions import broadcast_decision
from src.core.contracts.event import EventEnvelope
from src.events.envelopes import DecisionEventType, ExecutionEventType


class WebSocketEventHandler:
    """Broadcasts decision outcomes to connected WebSocket clients."""

    event_types = {
        DecisionEventType.DECISION_APPROVED,
        DecisionEventType.DECISION_REJECTED,
        ExecutionEventType.SIGNAL_PUBLISHED,
    }

    async def handle(self, event: EventEnvelope) -> None:
        if event.event_type == ExecutionEventType.SIGNAL_PUBLISHED:
            await broadcast_decision(
                decision_id=event.payload.get("decision_id", event.event_id),
                symbol=event.symbol,
                result="signal_published",
                correlation_id=event.correlation_id,
                side=event.payload.get("side"),
                confidence=event.payload.get("confidence"),
            )
            return
        if event.event_type == DecisionEventType.DECISION_APPROVED:
            fs = event.payload.get("final_signal") or {}
            await broadcast_decision(
                decision_id=event.payload["decision_id"],
                symbol=event.symbol,
                result="approved",
                correlation_id=event.correlation_id,
                side=fs.get("side"),
                confidence=fs.get("confidence"),
            )
        elif event.event_type == DecisionEventType.DECISION_REJECTED:
            await broadcast_decision(
                decision_id=event.payload["decision_id"],
                symbol=event.symbol,
                result="rejected",
                correlation_id=event.correlation_id,
                rejection_reason=event.payload.get("rejection_reason"),
                rejection_stage=event.payload.get("rejection_stage"),
            )
