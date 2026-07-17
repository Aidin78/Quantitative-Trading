from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class JobProgressHub:
    """In-process pub/sub for optimization/validation status snapshots.

    Queues use maxsize=1 and coalesce to the latest payload so chatty
    validation progress does not back up subscribers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(job_id)
        if not subscribers:
            return
        try:
            subscribers.remove(queue)
        except ValueError:
            return
        if not subscribers:
            self._subscribers.pop(job_id, None)

    def publish(self, job_id: str, payload: dict[str, Any]) -> None:
        subscribers = self._subscribers.get(job_id)
        if not subscribers:
            return
        for queue in list(subscribers):
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def clear(self) -> None:
        self._subscribers.clear()


job_progress = JobProgressHub()


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def sse_job_event_stream(
    job_id: str,
    *,
    initial: dict[str, Any],
    heartbeat_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Yield SSE frames: snapshot, then progress/terminal until done."""
    queue = job_progress.subscribe(job_id)
    try:
        yield format_sse("snapshot", initial)
        if initial.get("status") in TERMINAL_STATUSES:
            yield format_sse("terminal", initial)
            return

        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield ": ping\n\n"
                continue

            if payload.get("status") in TERMINAL_STATUSES:
                yield format_sse("terminal", payload)
                return
            yield format_sse("progress", payload)
    finally:
        job_progress.unsubscribe(job_id, queue)
