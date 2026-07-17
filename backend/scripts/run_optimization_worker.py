#!/usr/bin/env python3
"""Durable worker: dequeue and run optimization sweeps off the API process."""

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
from src.api.services.optimization_service import NAMESPACE, optimization_sweeps
from src.db.session import get_async_engine, init_db
from src.validation.optimization_job_executor import execute_optimization_sweep

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run durable optimization sweep worker")
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=5.0,
        help="BRPOP timeout in seconds between idle polls",
    )
    parser.add_argument("--no-db", action="store_true", help="Skip database init")
    return parser.parse_args()


async def _run_loop(*, poll_timeout: float, stop_event: asyncio.Event) -> None:
    persistence = optimization_sweeps._persistence
    if not isinstance(persistence, RedisJobPersistence):
        persistence = create_job_persistence(prefer_redis=True)
        if not isinstance(persistence, RedisJobPersistence):
            raise SystemExit(
                "Redis is required for the optimization worker. "
                "Set REDIS_URL and ensure Redis is reachable."
            )
        optimization_sweeps._persistence = persistence

    logger.info("Optimization worker listening on queue namespace=%s", NAMESPACE)
    while not stop_event.is_set():
        sweep_id = await asyncio.to_thread(
            persistence.blocking_dequeue,
            NAMESPACE,
            poll_timeout,
        )
        if sweep_id is None:
            continue
        sweep = optimization_sweeps.get(sweep_id)
        if sweep is None:
            logger.warning("Dequeued unknown sweep_id=%s; skipping", sweep_id)
            continue
        if sweep.status not in {"pending", "running"}:
            logger.info("Skipping sweep_id=%s status=%s", sweep_id, sweep.status)
            continue
        if sweep.cancel_requested:
            sweep.status = "cancelled"
            sweep.message = "Optimization cancelled."
            sweep.error = None
            optimization_sweeps.update(sweep)
            continue
        logger.info("Executing optimization sweep_id=%s", sweep_id)
        await execute_optimization_sweep(sweep_id, sweep.config)


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
    logger.info("Optimization worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
