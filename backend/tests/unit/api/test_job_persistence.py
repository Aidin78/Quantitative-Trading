from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.api.services.job_persistence import (
    InMemoryJobPersistence,
    RedisJobPersistence,
    create_job_persistence,
)
from src.api.services.optimization_service import (
    OptimizationSweep,
    OptimizationSweepStore,
    sweep_response,
)
from src.api.services.validation_service import ValidationJobStore, job_response
from src.core.settings import get_settings


def test_create_job_persistence_falls_back_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://invalid:59999/0")
    get_settings.cache_clear()
    persistence = create_job_persistence(prefer_redis=True)
    assert isinstance(persistence, InMemoryJobPersistence)


def test_in_memory_persistence_roundtrip() -> None:
    persistence = InMemoryJobPersistence()
    persistence.save("optimization", "sweep_1", {"id": "sweep_1", "status": "running"})
    assert persistence.has_active("optimization") is True
    loaded = persistence.load("optimization", "sweep_1")
    assert loaded is not None
    assert loaded["status"] == "running"
    persistence.save("optimization", "sweep_1", {"id": "sweep_1", "status": "completed"})
    assert persistence.has_active("optimization") is False


def test_redis_persistence_roundtrip() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    client = fakeredis.FakeRedis(decode_responses=True)
    persistence = RedisJobPersistence(client)
    persistence.save(
        "validation",
        "job_1",
        {"id": "job_1", "status": "running", "config": {}},
    )
    assert persistence.has_active("validation") is True
    assert persistence.load("validation", "job_1")["status"] == "running"
    persistence.save(
        "validation",
        "job_1",
        {"id": "job_1", "status": "completed", "config": {}},
    )
    assert persistence.has_active("validation") is False


def test_optimization_store_survives_local_clear() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = OptimizationSweepStore(persistence=persistence)
    sweep = store.create("sweep_restart", {"symbol": "BTC/USDT"})
    sweep.status = "completed"
    sweep.result_snapshot = {
        "sweep_id": "sweep_restart",
        "symbol": "BTC/USDT",
        "best_valid": True,
        "best": {"params": {"min_confidence": 0.7}, "trial_id": "t1"},
    }
    store.update(sweep)

    store.clear_local()
    restored = store.get("sweep_restart")
    assert restored is not None
    assert restored.status == "completed"
    assert restored.result is None
    assert restored.result_snapshot is not None
    payload = sweep_response(restored)
    assert payload["best"]["params"]["min_confidence"] == 0.7


def test_validation_store_marks_orphaned_running_as_failed() -> None:
    persistence = InMemoryJobPersistence()
    store = ValidationJobStore(persistence=persistence)
    job = store.create("job_orphan", {"symbol": "ETH/USDT"})
    job.status = "running"
    job.progress_current = 10
    job.progress_total = 100
    store.update(job)

    store.clear_local()
    restored = store.get("job_orphan")
    assert restored is not None
    assert restored.status == "failed"
    assert "restart" in (restored.error or "").lower()
    payload = job_response(restored)
    assert payload["status"] == "failed"


def test_has_active_sees_persisted_running_job() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    client = fakeredis.FakeRedis(decode_responses=True)
    persistence = RedisJobPersistence(client)
    writer = OptimizationSweepStore(persistence=persistence)
    reader = OptimizationSweepStore(persistence=persistence)

    sweep = writer.create("sweep_active", {})
    sweep.status = "running"
    writer.update(sweep)
    writer.clear_local()

    assert reader.has_active() is True
    # Hydration of an orphaned running job marks it failed and clears active.
    restored = reader.get("sweep_active")
    assert restored is not None
    assert restored.status == "failed"
    assert reader.has_active() is False


def test_sweep_created_at_roundtrip_iso() -> None:
    persistence = InMemoryJobPersistence()
    store = OptimizationSweepStore(persistence=persistence)
    sweep = OptimizationSweep(
        id="sweep_ts",
        status="pending",
        config={},
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    store.update(sweep)
    store.clear_local()
    restored = store.get("sweep_ts")
    assert restored is not None
    assert restored.created_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
