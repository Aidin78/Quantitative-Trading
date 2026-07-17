from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import redis

from src.core.settings import get_settings

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = frozenset({"pending", "running"})
COMPLETED_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
VALIDATION_PROGRESS_CHANNEL = "qtp:jobs:progress:validation"


class JobPersistence(Protocol):
    def save(self, namespace: str, job_id: str, record: dict[str, Any]) -> None: ...

    def load(self, namespace: str, job_id: str) -> dict[str, Any] | None: ...

    def has_active(self, namespace: str) -> bool: ...

    def clear_namespace(self, namespace: str) -> None: ...

    def supports_queue(self) -> bool: ...

    def enqueue(self, namespace: str, job_id: str) -> None: ...

    def blocking_dequeue(self, namespace: str, timeout: float) -> str | None: ...

    def publish_progress(self, namespace: str, payload: dict[str, Any]) -> None: ...


class InMemoryJobPersistence:
    """Process-local durable layer used when Redis is unavailable."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, dict[str, Any]]] = {}

    def save(self, namespace: str, job_id: str, record: dict[str, Any]) -> None:
        bucket = self._records.setdefault(namespace, {})
        bucket[job_id] = dict(record)

    def load(self, namespace: str, job_id: str) -> dict[str, Any] | None:
        record = self._records.get(namespace, {}).get(job_id)
        return dict(record) if record is not None else None

    def has_active(self, namespace: str) -> bool:
        for record in self._records.get(namespace, {}).values():
            if record.get("status") in ACTIVE_STATUSES:
                return True
        return False

    def clear_namespace(self, namespace: str) -> None:
        self._records.pop(namespace, None)

    def supports_queue(self) -> bool:
        return False

    def enqueue(self, namespace: str, job_id: str) -> None:
        raise RuntimeError("In-memory job persistence does not support an external queue")

    def blocking_dequeue(self, namespace: str, timeout: float) -> str | None:
        return None

    def publish_progress(self, namespace: str, payload: dict[str, Any]) -> None:
        return


class RedisJobPersistence:
    """Redis hash + active set for cross-restart / multi-worker job visibility."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def _key(self, namespace: str, job_id: str) -> str:
        return f"qtp:jobs:{namespace}:{job_id}"

    def _active_key(self, namespace: str) -> str:
        return f"qtp:jobs:{namespace}:active"

    def _queue_key(self, namespace: str) -> str:
        return f"qtp:jobs:{namespace}:queue"

    def _progress_channel(self, namespace: str) -> str:
        return f"qtp:jobs:progress:{namespace}"

    def save(self, namespace: str, job_id: str, record: dict[str, Any]) -> None:
        key = self._key(namespace, job_id)
        payload = json.dumps(record, default=str)
        status = record.get("status")
        pipe = self._client.pipeline()
        if status in ACTIVE_STATUSES:
            pipe.set(key, payload)
            pipe.sadd(self._active_key(namespace), job_id)
        else:
            pipe.set(key, payload, ex=COMPLETED_TTL_SECONDS)
            pipe.srem(self._active_key(namespace), job_id)
        pipe.execute()

    def load(self, namespace: str, job_id: str) -> dict[str, Any] | None:
        raw = self._client.get(self._key(namespace, job_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None

    def has_active(self, namespace: str) -> bool:
        active_key = self._active_key(namespace)
        for job_id in list(self._client.smembers(active_key)):
            record = self.load(namespace, str(job_id))
            if record is None or record.get("status") not in ACTIVE_STATUSES:
                self._client.srem(active_key, job_id)
                continue
            return True
        return False

    def clear_namespace(self, namespace: str) -> None:
        pattern = f"qtp:jobs:{namespace}:*"
        keys = list(self._client.scan_iter(match=pattern, count=100))
        if keys:
            self._client.delete(*keys)

    def supports_queue(self) -> bool:
        return True

    def enqueue(self, namespace: str, job_id: str) -> None:
        self._client.lpush(self._queue_key(namespace), job_id)

    def blocking_dequeue(self, namespace: str, timeout: float) -> str | None:
        # redis-py BRPOP timeout is integer seconds; 0 blocks forever.
        wait = max(1, int(timeout))
        result = self._client.brpop(self._queue_key(namespace), timeout=wait)
        if result is None:
            return None
        _key, job_id = result
        return str(job_id)

    def publish_progress(self, namespace: str, payload: dict[str, Any]) -> None:
        channel = self._progress_channel(namespace)
        self._client.publish(channel, json.dumps(payload, default=str))


def create_job_persistence(*, prefer_redis: bool = True) -> JobPersistence:
    if prefer_redis:
        try:
            settings = get_settings()
            client = redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            logger.info("Using RedisJobPersistence at %s", settings.redis_url)
            return RedisJobPersistence(client)
        except Exception as exc:
            logger.warning("Redis job store unavailable (%s); using in-memory persistence", exc)
    return InMemoryJobPersistence()
