from __future__ import annotations

from datetime import UTC, datetime, timedelta


class WallClock:
    def __init__(self, event_time: datetime | None = None) -> None:
        self._event_time = event_time

    def set_event_time(self, event_time: datetime) -> None:
        self._event_time = event_time

    def now_event_time(self) -> datetime:
        if self._event_time is not None:
            return self._event_time
        return datetime.now(UTC)

    def now_processing_time(self) -> datetime:
        return datetime.now(UTC)


class SimulatedClock:
    def __init__(
        self,
        *,
        event_time: datetime,
        processing_time: datetime | None = None,
        processing_offset: timedelta = timedelta(seconds=1),
    ) -> None:
        self._event_time = event_time
        self._processing_time = processing_time or (event_time + processing_offset)

    def set_event_time(self, event_time: datetime) -> None:
        self._event_time = event_time

    def set_processing_time(self, processing_time: datetime) -> None:
        self._processing_time = processing_time

    def now_event_time(self) -> datetime:
        return self._event_time

    def now_processing_time(self) -> datetime:
        return self._processing_time
