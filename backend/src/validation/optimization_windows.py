from __future__ import annotations

from datetime import datetime, timedelta


def split_train_test(
    start: datetime,
    end: datetime,
    *,
    train_ratio: float,
) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    total = end - start
    if total <= timedelta(0):
        raise ValueError("end must be after start")
    train_end = start + timedelta(seconds=total.total_seconds() * train_ratio)
    return (start, train_end), (train_end, end)


def split_holdout(
    start: datetime,
    end: datetime,
    *,
    holdout_ratio: float,
) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime] | None]:
    if holdout_ratio <= 0:
        return (start, end), None
    if not 0 < holdout_ratio < 1:
        raise ValueError("holdout_ratio must be between 0 and 1")
    total = end - start
    if total <= timedelta(0):
        raise ValueError("end must be after start")
    opt_end = start + timedelta(seconds=total.total_seconds() * (1 - holdout_ratio))
    return (start, opt_end), (opt_end, end)
