from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now_event_time(self) -> datetime: ...

    def now_processing_time(self) -> datetime: ...
