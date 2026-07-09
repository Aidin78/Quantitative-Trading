from __future__ import annotations

from datetime import UTC, datetime

from src.validation.walk_forward import (
    build_anchored_walk_forward_windows,
    build_walk_forward_windows,
)


def test_anchored_walk_forward_expands_train_from_start() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    anchored = build_anchored_walk_forward_windows(start, end, windows=3, train_ratio=0.7)
    fixed = build_walk_forward_windows(start, end, windows=3, train_ratio=0.7)
    assert len(anchored) == 3
    assert anchored[-1].train_start == start
    assert fixed[0].train_start == anchored[0].train_start
    assert anchored[-1].train_start < fixed[-1].train_start
