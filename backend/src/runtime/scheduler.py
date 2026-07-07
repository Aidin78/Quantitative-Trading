"""APScheduler helpers for live runtime (see live_manager for orchestration)."""

from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger


def cron_for_timeframe(timeframe: str) -> CronTrigger:
    if timeframe == "1h":
        return CronTrigger(minute=1)
    if timeframe == "4h":
        return CronTrigger(hour="*/4", minute=1)
    if timeframe == "1d":
        return CronTrigger(hour=0, minute=5)
    return CronTrigger(minute="*/15")
