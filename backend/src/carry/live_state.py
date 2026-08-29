"""Persisted state for the live/testnet basis-carry runner.

One JSON file under ``backend/data/`` holds the runner's position, cash, and
the last market mark, so the process can restart and so a read-only consumer
(the ``/api/v1/portfolio`` endpoint) can show the sleeve without touching an
exchange. ``scripts/run_carry_live.py`` is the sole writer.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.carry.position_manager import CarryPositionState

STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "carry_live_state.json"


def load_live_state() -> dict[str, Any] | None:
    """The raw persisted dict, or ``None`` when the runner has never run."""
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_position() -> tuple[CarryPositionState, float, float | None]:
    """``(position, cash, spot_baseline)`` — defaults for a fresh runner."""
    raw = load_live_state()
    if raw is None:
        return CarryPositionState(), 0.0, None
    st = raw["state"]
    return (
        CarryPositionState(
            spot_qty=st["spot_qty"],
            perp_qty=st["perp_qty"],
            spot_entry_px=st["spot_entry_px"],
            perp_entry_px=st["perp_entry_px"],
            accrued_funding=st["accrued_funding"],
            flips=st["flips"],
        ),
        raw["cash"],
        raw.get("spot_baseline"),
    )


def save_live_state(
    state: CarryPositionState,
    cash: float,
    spot_baseline: float | None,
    *,
    symbol: str | None = None,
    mark: dict[str, Any] | None = None,
) -> None:
    """Write the state file. ``mark`` (last prices / funding / equity) and
    ``symbol`` carry forward from the previous write when not supplied."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    prev = load_live_state() or {}
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "symbol": symbol or prev.get("symbol"),
        "cash": cash,
        "spot_baseline": spot_baseline,
        "state": asdict(state),
        "mark": prev.get("mark") if mark is None else mark,
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2))
