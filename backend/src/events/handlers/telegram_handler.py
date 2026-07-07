from __future__ import annotations

import logging

from telegram import Bot
from telegram.error import TelegramError

from src.core.contracts.event import EventEnvelope
from src.core.settings import get_settings
from src.events.envelopes import ExecutionEventType

logger = logging.getLogger(__name__)


class TelegramEventHandler:
    """Sends approved signals to Telegram on SignalPublished events."""

    event_types = {ExecutionEventType.SIGNAL_PUBLISHED}

    def __init__(self, *, bot_token: str | None = None, channel_id: str | None = None) -> None:
        settings = get_settings()
        self._token = bot_token if bot_token is not None else settings.telegram_bot_token
        self._channel_id = channel_id if channel_id is not None else settings.telegram_channel_id
        self._bot: Bot | None = Bot(self._token) if self._token else None

    def is_configured(self) -> bool:
        return bool(self._token and self._channel_id and self._bot)

    async def ping(self) -> bool:
        if not self.is_configured() or self._bot is None:
            return False
        try:
            await self._bot.get_me()
            return True
        except TelegramError:
            return False

    async def handle(self, event: EventEnvelope) -> None:
        if not self.is_configured() or self._bot is None:
            return
        payload = event.payload
        message = self._format_message(event.symbol, event.timeframe, payload)
        for attempt in range(3):
            try:
                await self._bot.send_message(
                    chat_id=self._channel_id,
                    text=message,
                    parse_mode=None,
                )
                return
            except TelegramError as exc:
                logger.warning("Telegram send failed (attempt %s): %s", attempt + 1, exc)
        logger.error("Telegram send failed after retries for %s", event.correlation_id)

    @staticmethod
    def _format_message(symbol: str, timeframe: str, payload: dict) -> str:
        side = payload.get("side", "?")
        emoji = "🟢" if side == "BUY" else "🔴"
        entry = payload.get("entry_price")
        sl = payload.get("stop_loss")
        tp = payload.get("take_profit")
        confidence = payload.get("confidence", 0)
        providers = payload.get("provider_ids") or []
        rr = payload.get("risk_reward")
        provider_line = ", ".join(str(p).replace("_", " ").title() for p in providers) or "—"
        sl_pct = ""
        if entry and sl:
            sl_pct = f" ({((sl - entry) / entry * 100):+.2f}%)"
        tp_pct = ""
        if entry and tp:
            tp_pct = f" ({((tp - entry) / entry * 100):+.2f}%)"
        return (
            f"{emoji} {side} | {symbol} | {timeframe.upper()}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 Entry: {entry}\n"
            f"🛑 SL: {sl}{sl_pct}\n"
            f"🎯 TP: {tp}{tp_pct}\n"
            f"📊 R:R = {rr}\n\n"
            f"💪 Confidence: {confidence * 100:.0f}%\n"
            f"✅ Providers: {provider_line}\n\n"
            f"⚠️ Not financial advice"
        )
