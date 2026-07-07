"""Send a test Telegram message using TELEGRAM_* from .env."""

from __future__ import annotations

import asyncio

from src.core.settings import get_settings
from src.events.handlers.telegram_client import build_telegram_bot
from src.events.handlers.telegram_handler import TelegramEventHandler


async def main() -> int:
    get_settings.cache_clear()
    handler = TelegramEventHandler()
    if not handler.is_configured():
        print("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
        return 1
    if not await handler.ping():
        print("Telegram bot token invalid or API unreachable")
        if not get_settings().telegram_proxy_url:
            print(
                "Tip: set TELEGRAM_PROXY_URL if Telegram API is blocked (e.g. socks5://127.0.0.1:1080)"
            )
        return 1
    settings = get_settings()
    bot = build_telegram_bot(settings)
    assert bot is not None
    await bot.send_message(
        chat_id=settings.telegram_channel_id,
        text="✅ Quantitative Trading Platform — Telegram test OK",
    )
    print("Test message sent successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
