from __future__ import annotations

from src.events.handlers.telegram_handler import TelegramEventHandler
from src.runtime.live_manager import live_manager


async def _ping_telegram_alerts() -> bool:
    telegram = TelegramEventHandler()
    return await telegram.ping() if telegram.is_configured() else False


live_manager.set_alert_pinger(_ping_telegram_alerts)


def get_live_manager():
    return live_manager
