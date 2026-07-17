#!/usr/bin/env python3
"""Durable worker: dequeue and run validation jobs off the API process."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.api.services.job_persistence import RedisJobPersistence, create_job_persistence
from src.api.services.validation_service import NAMESPACE, validation_jobs
from src.db.session import get_async_engine, init_db
from src.validation.job_executor import execute_validation_job

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run durable validation job worker")
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=5.0,
        help="BRPOP timeout in seconds between idle polls",
    )
    parser.add_argument("--no-db", action="store_true", help="Skip database init")
    return parser.parse_args()


async def _run_loop(*, poll_timeout: float, stop_event: asyncio.Event) -> None:
    persistence = validation_jobs._persistence
    if not isinstance(persistence, RedisJobPersistence):
        # Force Redis — worker cannot run against in-memory API state.
        persistence = create_job_persistence(prefer_redis=True)
        if not isinstance(persistence, RedisJobPersistence):
            raise SystemExit(
                "Redis is required for the validation worker. "
                "Set REDIS_URL and ensure Redis is reachable."
            )
        validation_jobs._persistence = persistence

    logger.info("Validation worker listening on queue namespace=%s", NAMESPACE)
    while not stop_event.is_set():
        job_id = await asyncio.to_thread(
            persistence.blocking_dequeue,
            NAMESPACE,
            poll_timeout,
        )
        if job_id is None:
            continue
        job = validation_jobs.get(job_id)
        if job is None:
            logger.warning("Dequeued unknown job_id=%s; skipping", job_id)
            continue
        if job.status not in {"pending", "running"}:
            logger.info("Skipping job_id=%s status=%s", job_id, job.status)
            continue
        if job.cancel_requested:
            job.status = "cancelled"
            job.message = "Validation cancelled."
            job.error = None
            validation_jobs.update(job)
            continue
        logger.info("Executing validation job_id=%s", job_id)
        await execute_validation_job(job_id, job.config)


async def _main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not args.no_db:
        await init_db(get_async_engine())

    stop_event = asyncio.Event()

    def _handle_sig(*_args: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    await _run_loop(poll_timeout=args.poll_timeout, stop_event=stop_event)
    logger.info("Validation worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
