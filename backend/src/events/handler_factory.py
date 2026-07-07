from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.contracts.event import EventHandler
from src.events.handlers.database_handler import DatabaseEventHandler
from src.events.handlers.telegram_handler import TelegramEventHandler
from src.events.handlers.websocket_handler import WebSocketEventHandler


def build_handlers(
    mode: Literal["paper", "live"],
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    persist_db: bool = True,
) -> list[EventHandler]:
    handlers: list[EventHandler] = [WebSocketEventHandler()]
    if persist_db and session_factory is not None:
        handlers.append(DatabaseEventHandler(session_factory))
    if mode == "live":
        handlers.append(TelegramEventHandler())
    return handlers
