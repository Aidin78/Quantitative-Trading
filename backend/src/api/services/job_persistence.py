from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Protocol

import redis

from src.core.settings import get_settings

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = frozenset({"pending", "running"})
COMPLETED_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
VALIDATION_PROGRESS_CHANNEL = "qtp:jobs:progress:validation"
OPTIMIZATION_PROGRESS_CHANNEL = "qtp:jobs:progress:optimization"

# How long a dequeued-but-unacked job may sit in the processing list before a
# reaper considers the worker that took it dead and puts it back on the queue.
PROCESSING_LEASE_SECONDS = 15 * 60


def progress_channel(namespace: str) -> str:
    return f"qtp:jobs:progress:{namespace}"


class JobPersistence(Protocol):
    def save(self, namespace: str, job_id: str, record: dict[str, Any]) -> None: ...

    def load(self, namespace: str, job_id: str) -> dict[str, Any] | None: ...

    def has_active(self, namespace: str) -> bool: ...

    def clear_namespace(self, namespace: str) -> None: ...

    def supports_queue(self) -> bool: ...

    def enqueue(self, namespace: str, job_id: str) -> None: ...

    def blocking_dequeue(self, namespace: str, timeout: float) -> str | None: ...

    def ack(self, namespace: str, job_id: str) -> None: ...

    def requeue_stale(self, namespace: str) -> list[str]: ...

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

    def ack(self, namespace: str, job_id: str) -> None:
        return

    def requeue_stale(self, namespace: str) -> list[str]:
        return []

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

    def _processing_key(self, namespace: str) -> str:
        return f"qtp:jobs:{namespace}:processing"

    def _lease_key(self, namespace: str, job_id: str) -> str:
        return f"qtp:jobs:{namespace}:lease:{job_id}"

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
        """Move one job from the queue to the processing list and return its id.

        The job stays on the processing list (with a lease TTL) until the
        caller calls ``ack``. If the worker crashes before acking, the job is
        never lost — ``requeue_stale`` (invoked by other workers/a reaper)
        puts it back on the queue once its lease expires.
        """
        # redis-py BLMOVE timeout is float seconds; 0 blocks forever.
        wait = max(1, int(timeout))
        job_id = self._client.blmove(
            self._queue_key(namespace),
            self._processing_key(namespace),
            timeout=wait,
            src="RIGHT",
            dest="LEFT",
        )
        if job_id is None:
            return None
        job_id = str(job_id)
        self._client.set(
            self._lease_key(namespace, job_id),
            str(uuid.uuid4()),
            ex=PROCESSING_LEASE_SECONDS,
        )
        return job_id

    def ack(self, namespace: str, job_id: str) -> None:
        """Mark a dequeued job as fully processed, removing it from the processing list."""
        pipe = self._client.pipeline()
        pipe.lrem(self._processing_key(namespace), 0, job_id)
        pipe.delete(self._lease_key(namespace, job_id))
        pipe.execute()

    def requeue_stale(self, namespace: str) -> list[str]:
        """Put back any processing-list job whose lease has expired (worker died).

        Safe to call from multiple workers concurrently — a job is only
        requeued once per expired lease, since the lease key is deleted (via
        GETDEL) atomically before it is pushed back onto the queue.
        """
        processing_key = self._processing_key(namespace)
        job_ids = [str(j) for j in self._client.lrange(processing_key, 0, -1)]
        requeued: list[str] = []
        for job_id in job_ids:
            lease = self._client.getdel(self._lease_key(namespace, job_id))
            if lease is None:
                # Lease already expired (or already reaped) — reclaim it.
                removed = self._client.lrem(processing_key, 1, job_id)
                if removed:
                    self._client.lpush(self._queue_key(namespace), job_id)
                    requeued.append(job_id)
        return requeued

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
