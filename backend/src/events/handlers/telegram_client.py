from __future__ import annotations

from telegram import Bot
from telegram.request import HTTPXRequest

from src.core.settings import Settings, get_settings


def build_telegram_bot(
    settings: Settings | None = None,
    *,
    token: str | None = None,
) -> Bot | None:
    """Build a Bot client; respects TELEGRAM_PROXY_URL and ignores broken system proxies."""
    cfg = settings or get_settings()
    bot_token = token or cfg.telegram_bot_token
    if not bot_token:
        return None
    request_kwargs: dict = {
        "connect_timeout": 20.0,
        "read_timeout": 20.0,
    }
    if cfg.telegram_proxy_url:
        request_kwargs["proxy"] = cfg.telegram_proxy_url
    else:
        request_kwargs["httpx_kwargs"] = {"trust_env": False}
    return Bot(bot_token, request=HTTPXRequest(**request_kwargs))
