from __future__ import annotations

import logging

from src.core.contracts.event import EventEnvelope

logger = logging.getLogger(__name__)


class LoggingEventHandler:
    event_types: set[str] = set()

    async def handle(self, event: EventEnvelope) -> None:
        logger.info(
            "event %s family=%s correlation=%s",
            event.event_type,
            event.event_family,
            event.correlation_id,
        )
