from __future__ import annotations

from src.core.contracts.event import EventEnvelope


def build_causal_graph(events: list[EventEnvelope]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    by_id: dict[str, EventEnvelope] = {}

    for event in events:
        by_id[event.event_id] = event
        nodes.append(
            {
                "id": event.event_id,
                "event_type": event.event_type,
                "event_family": event.event_family.value,
                "event_time": event.event_time.isoformat(),
            }
        )
        if event.causation_id and event.causation_id in by_id:
            edges.append(
                {
                    "from": event.causation_id,
                    "to": event.event_id,
                    "relation": "caused_by",
                }
            )
        elif event.causation_id:
            edges.append(
                {
                    "from": event.causation_id,
                    "to": event.event_id,
                    "relation": "caused_by",
                }
            )

    roots = [n["id"] for n in nodes if not any(e["to"] == n["id"] for e in edges)]
    return {"nodes": nodes, "edges": edges, "roots": roots}
