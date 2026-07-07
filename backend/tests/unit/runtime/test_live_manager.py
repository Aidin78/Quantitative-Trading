from __future__ import annotations

import asyncio

import pytest

from src.runtime.live_manager import LiveRuntimeManager


class _FakeDecision:
    is_approved = False


class _FakeCycleResult:
    decision = _FakeDecision()


@pytest.mark.asyncio
async def test_stop_while_run_cycle_in_progress() -> None:
    manager = LiveRuntimeManager()
    cycle_started = asyncio.Event()
    release_cycle = asyncio.Event()

    async def fake_platform_run_cycle(*_args, **_kwargs):
        cycle_started.set()
        await release_cycle.wait()
        return _FakeCycleResult()

    await manager.start(mode="paper", jobs=[("BTC/USDT", "1h")])
    assert manager._stack is not None  # noqa: SLF001
    manager._stack.runtime.run_cycle = fake_platform_run_cycle  # type: ignore[method-assign]

    cycle_task = asyncio.create_task(manager.run_cycle("BTC/USDT", "1h"))
    await asyncio.wait_for(cycle_started.wait(), timeout=2.0)

    stop_result = await asyncio.wait_for(manager.stop(), timeout=2.0)
    assert stop_result["status"] == "stopped"

    release_cycle.set()
    await cycle_task


@pytest.mark.asyncio
async def test_set_mode_does_not_deadlock_when_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LiveRuntimeManager()

    async def fake_rebuild(mode: str) -> None:
        manager._stack = type("S", (), {"provider": None, "runtime": None})()  # noqa: SLF001
        manager._state.exchange_connected = True  # noqa: SLF001
        manager._state.alerts_connected = False  # noqa: SLF001

    monkeypatch.setattr(manager, "_rebuild_stack", fake_rebuild)

    await manager.start(mode="paper", jobs=[("BTC/USDT", "1h")])

    status = await asyncio.wait_for(manager.set_mode("live"), timeout=2.0)

    assert status["status"] == "running"
    assert status["mode"] == "live"
    await manager.stop()
