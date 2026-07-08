from __future__ import annotations

from datetime import UTC, datetime

from src.data.market_cache import resolve_range, subtract_months


def test_subtract_months_handles_year_boundary() -> None:
    end = datetime(2026, 3, 15, tzinfo=UTC)
    start = subtract_months(end, 3)
    assert start == datetime(2025, 12, 15, tzinfo=UTC)


def test_resolve_range_uses_months_when_start_missing() -> None:
    start, end = resolve_range(
        start_date=None,
        end_date="2026-07-08",
        months=3,
    )
    assert end == datetime(2026, 7, 8, tzinfo=UTC)
    assert start == datetime(2026, 4, 8, tzinfo=UTC)


def test_resolve_range_prefers_explicit_start() -> None:
    start, end = resolve_range(
        start_date="2026-01-01",
        end_date="2026-01-31",
        months=3,
    )
    assert start == datetime(2026, 1, 1, tzinfo=UTC)
    assert end == datetime(2026, 1, 31, tzinfo=UTC)
