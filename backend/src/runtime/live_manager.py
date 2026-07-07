from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.api.services.live_runner import (
    LiveStack,
    build_live_stack,
    check_connectivity,
    default_live_jobs,
)
from src.governance.live_gate import LiveGovernanceGate
from src.runtime.scheduler import cron_for_timeframe


def _job_id(symbol: str, timeframe: str) -> str:
    return f"live_{symbol.replace('/', '_')}_{timeframe}"


def _job_next_run(scheduler: AsyncIOScheduler, job_id: str) -> str | None:
    job = scheduler.get_job(job_id)
    if job is None:
        return None
    next_time = getattr(job, "next_run_time", None) or getattr(job, "next_fire_time", None)
    if next_time is None:
        return None
    return next_time.astimezone(UTC).isoformat()


@dataclass
class LiveJobInfo:
    symbol: str
    timeframe: str
    next_run_at: str | None = None


@dataclass
class LiveRuntimeState:
    status: Literal["stopped", "running", "paused"] = "stopped"
    mode: Literal["paper", "live"] = "paper"
    last_run_at: datetime | None = None
    last_signal_at: datetime | None = None
    last_error: str | None = None
    exchange_connected: bool = False
    alerts_connected: bool = False
    revision_id: str | None = None
    jobs: list[LiveJobInfo] = field(default_factory=list)


class LiveRuntimeManager:
    """Singleton manager for live/paper scheduler and runtime stack."""

    def __init__(self) -> None:
        self._state = LiveRuntimeState()
        self._scheduler: AsyncIOScheduler | None = None
        self._stack: LiveStack | None = None
        self._lock = asyncio.Lock()
        self._gate = LiveGovernanceGate()

    @property
    def state(self) -> LiveRuntimeState:
        return self._state

    def status_dict(self) -> dict:
        return {
            "status": self._state.status,
            "mode": self._state.mode,
            "exchange_connected": self._state.exchange_connected,
            "alerts_connected": self._state.alerts_connected,
            "last_run_at": self._state.last_run_at.isoformat() if self._state.last_run_at else None,
            "last_signal_at": self._state.last_signal_at.isoformat()
            if self._state.last_signal_at
            else None,
            "last_error": self._state.last_error,
            "revision_id": self._state.revision_id,
            "jobs": [
                {"symbol": j.symbol, "timeframe": j.timeframe, "next_run_at": j.next_run_at}
                for j in self._state.jobs
            ],
        }

    async def start(
        self,
        *,
        mode: Literal["paper", "live"] = "paper",
        jobs: list[tuple[str, str]] | None = None,
        revision_id: str | None = None,
    ) -> dict:
        if not self._gate.allow_start(revision_id):
            raise ValueError(
                "Live start blocked by governance gate (revision_id required in production)"
            )
        async with self._lock:
            if self._scheduler is not None and self._state.status == "running":
                return self.status_dict()
            await self._rebuild_stack(mode)
            self._state.mode = mode
            self._state.revision_id = revision_id
            self._state.status = "running"
            self._state.jobs = []
            job_list = jobs or default_live_jobs()
            self._scheduler = AsyncIOScheduler()
            for symbol, timeframe in job_list:
                trigger = cron_for_timeframe(timeframe)
                job_id = _job_id(symbol, timeframe)

                def make_job(sym: str = symbol, tf: str = timeframe):
                    async def _job() -> None:
                        await self.run_cycle(sym, tf)

                    return _job

                self._scheduler.add_job(
                    make_job(),
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                )
            self._scheduler.start()
            self._state.jobs = []
            for symbol, timeframe in job_list:
                job_id = _job_id(symbol, timeframe)
                next_at = _job_next_run(self._scheduler, job_id)
                self._state.jobs.append(
                    LiveJobInfo(symbol=symbol, timeframe=timeframe, next_run_at=next_at)
                )
            return self.status_dict()

    async def stop(self) -> dict:
        async with self._lock:
            if self._scheduler is not None:
                try:
                    self._scheduler.shutdown(wait=False)
                except Exception:
                    pass
                self._scheduler = None
            self._stack = None
            self._state.status = "stopped"
            self._state.jobs = []
            return self.status_dict()

    async def set_mode(self, mode: Literal["paper", "live"]) -> dict:
        async with self._lock:
            was_running = self._state.status == "running"
            jobs = [(j.symbol, j.timeframe) for j in self._state.jobs]
            revision_id = self._state.revision_id
            if self._scheduler is not None:
                try:
                    self._scheduler.shutdown(wait=False)
                except Exception:
                    pass
                self._scheduler = None
            self._state.status = "stopped"
            self._stack = None
            if was_running and jobs:
                return await self.start(mode=mode, jobs=jobs, revision_id=revision_id)
            self._state.mode = mode
            return self.status_dict()

    async def run_cycle(self, symbol: str, timeframe: str) -> None:
        async with self._lock:
            try:
                if self._stack is None:
                    await self._rebuild_stack(self._state.mode)
                assert self._stack is not None
                ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
                corr = f"live_{symbol.replace('/', '')}_{timeframe}_{ts}"
                result = await self._stack.runtime.run_cycle(
                    symbol,
                    timeframe,
                    correlation_id=corr,
                    revision_id=self._state.revision_id,
                )
                self._state.last_run_at = datetime.now(UTC)
                self._state.last_error = None
                if result.decision.is_approved:
                    self._state.last_signal_at = datetime.now(UTC)
            except Exception as exc:
                self._state.last_error = str(exc)
                raise

    async def _rebuild_stack(self, mode: Literal["paper", "live"]) -> None:
        self._stack = await build_live_stack(mode)
        exchange_ok, alerts_ok = await check_connectivity(mode, self._stack.provider)
        self._state.exchange_connected = exchange_ok
        self._state.alerts_connected = alerts_ok


live_manager = LiveRuntimeManager()
