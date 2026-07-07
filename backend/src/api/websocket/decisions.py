from __future__ import annotations

import json
from typing import Any


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[Any] = []

    async def connect(self, websocket: Any) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: Any) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, event: str, data: dict) -> None:
        message = json.dumps({"event": event, "data": data})
        dead: list[Any] = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


decision_ws_manager = ConnectionManager()


async def broadcast_decision(
    *,
    decision_id: str,
    symbol: str,
    result: str,
    correlation_id: str,
    rejection_reason: str | None = None,
    rejection_stage: str | None = None,
    side: str | None = None,
    confidence: float | None = None,
) -> None:
    event = f"decision.{result}"
    data: dict[str, Any] = {
        "id": decision_id,
        "symbol": symbol,
        "correlation_id": correlation_id,
        "result": result,
    }
    if result == "approved":
        data["side"] = side
        data["confidence"] = confidence
    else:
        data["reason"] = rejection_reason
        data["rejection_stage"] = rejection_stage
    await decision_ws_manager.broadcast(event, data)
