from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.validation.harness import ValidationConfig


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


def build_walk_forward_windows(
    start: datetime,
    end: datetime,
    *,
    windows: int = 3,
    train_ratio: float = 0.7,
) -> list[WalkForwardWindow]:
    if windows < 1:
        raise ValueError("windows must be >= 1")
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    total = end - start
    if total <= timedelta(0):
        raise ValueError("end must be after start")
    window_size = total / windows
    result: list[WalkForwardWindow] = []
    for i in range(windows):
        w_start = start + window_size * i
        w_end = start + window_size * (i + 1)
        train_span = w_end - w_start
        train_end = w_start + timedelta(seconds=train_span.total_seconds() * train_ratio)
        result.append(
            WalkForwardWindow(
                index=i,
                train_start=w_start,
                train_end=train_end,
                test_start=train_end,
                test_end=w_end,
            )
        )
    return result


def window_to_validation_config(
    window: WalkForwardWindow,
    *,
    symbol: str,
    timeframe: str,
) -> ValidationConfig:
    return ValidationConfig(
        symbol=symbol,
        timeframe=timeframe,
        start=window.test_start.replace(tzinfo=UTC)
        if window.test_start.tzinfo is None
        else window.test_start,
        end=window.test_end.replace(tzinfo=UTC)
        if window.test_end.tzinfo is None
        else window.test_end,
    )
