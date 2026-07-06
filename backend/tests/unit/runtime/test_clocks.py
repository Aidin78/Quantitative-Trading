from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.runtime.clocks import SimulatedClock, WallClock


def test_wall_clock_uses_injected_event_time() -> None:
    event_time = datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC)
    clock = WallClock(event_time=event_time)
    assert clock.now_event_time() == event_time


def test_simulated_clock_separates_event_and_processing_time() -> None:
    event_time = datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC)
    processing_time = event_time + timedelta(seconds=2)
    clock = SimulatedClock(event_time=event_time, processing_time=processing_time)
    assert clock.now_event_time() == event_time
    assert clock.now_processing_time() == processing_time
    assert clock.now_event_time() != clock.now_processing_time()
