from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.contracts.event import EventEnvelope, EventFamily
from src.events.envelopes import ExecutionEventType
from src.events.handlers.telegram_handler import TelegramEventHandler


@pytest.mark.asyncio
async def test_telegram_handler_formats_and_sends() -> None:
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    with patch(
        "src.events.handlers.telegram_handler.build_telegram_bot",
        return_value=mock_bot,
    ):
        handler = TelegramEventHandler(bot_token="token", channel_id="channel")
    event = EventEnvelope(
        event_id="evt_1",
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.SIGNAL_PUBLISHED,
        event_time=datetime.now(UTC),
        processing_time=datetime.now(UTC),
        correlation_id="cycle_1",
        cycle_id="cycle_1",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="live",
        payload={
            "side": "BUY",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "take_profit": 104.0,
            "confidence": 0.8,
            "risk_reward": 2.0,
            "provider_ids": ["ema_crossover"],
        },
    )
    await handler.handle(event)
    mock_bot.send_message.assert_awaited_once()
    text = (
        mock_bot.send_message.await_args.kwargs.get("text")
        or mock_bot.send_message.await_args.args[1]
    )
    assert "BUY" in text
    assert "BTC/USDT" in text
