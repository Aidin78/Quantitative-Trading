"""Bridge Redis validation progress pub/sub into the in-process SSE hub."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.api.services.job_persistence import VALIDATION_PROGRESS_CHANNEL
from src.api.services.job_progress import job_progress
from src.core.settings import get_settings

logger = logging.getLogger(__name__)


async def run_validation_progress_bridge(stop_event: asyncio.Event) -> None:
    """Forward ``qtp:jobs:progress:validation`` messages into ``JobProgressHub``.

    No-ops (with a warning) when Redis is unavailable so local in-memory
    create_task execution still works without a bridge.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis.asyncio unavailable; validation progress bridge disabled")
        await stop_event.wait()
        return

    settings = get_settings()
    client: Any = None
    pubsub: Any = None
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        pubsub = client.pubsub()
        await pubsub.subscribe(VALIDATION_PROGRESS_CHANNEL)
        logger.info("Validation progress bridge subscribed to %s", VALIDATION_PROGRESS_CHANNEL)
        while not stop_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None or message.get("type") != "message":
                continue
            raw = message.get("data")
            if not isinstance(raw, str):
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            job_id = payload.get("id")
            if not isinstance(job_id, str) or not job_id:
                continue
            job_progress.publish(job_id, payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Validation progress bridge stopped (%s)", exc)
        await stop_event.wait()
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(VALIDATION_PROGRESS_CHANNEL)
                await pubsub.aclose()
            except Exception:
                pass
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
