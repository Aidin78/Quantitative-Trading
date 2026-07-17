from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from src.validation.optimization_scoring import TrialResult


@dataclass
class ProgressEvent:
    current: int
    total: int
    phase: Literal["train", "test", "refine"]
    stage: Literal["start", "done"]
    trial: TrialResult | None = None
    train_count: int = 0
    test_count: int = 0
    detail: str = ""


ProgressCallback = Callable[[ProgressEvent], Awaitable[None] | None]


async def emit_progress(
    on_progress: ProgressCallback | None,
    event: ProgressEvent,
) -> None:
    if on_progress is None:
        return
    maybe = on_progress(event)
    if maybe is not None:
        await maybe
