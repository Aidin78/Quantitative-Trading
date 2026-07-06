from __future__ import annotations

import pytest

from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from tests.mocks.fixtures import utc_now


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine(load_engine_config())


@pytest.fixture
def times() -> dict:
    now = utc_now()
    return {"event_time": now, "decision_time": now}
