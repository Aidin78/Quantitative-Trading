from __future__ import annotations

import pytest

from src.carry import live_state
from src.carry.position_manager import CarryPositionState


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "carry_live_state.json"
    monkeypatch.setattr(live_state, "STATE_PATH", path)
    return path


def test_load_missing_returns_none_and_defaults(state_file):
    assert live_state.load_live_state() is None
    pos, cash, baseline = live_state.load_position()
    assert pos == CarryPositionState()
    assert cash == 0.0
    assert baseline is None


def test_round_trip(state_file):
    pos = CarryPositionState(spot_qty=0.5, perp_qty=0.5, spot_entry_px=100.0, perp_entry_px=101.0)
    live_state.save_live_state(pos, cash=250.0, spot_baseline=1.0, symbol="BTC/USDT")
    loaded, cash, baseline = live_state.load_position()
    assert loaded == pos
    assert cash == 250.0
    assert baseline == 1.0
    assert live_state.load_live_state()["symbol"] == "BTC/USDT"


def test_mark_and_symbol_carry_forward_when_omitted(state_file):
    pos = CarryPositionState(spot_qty=0.5, perp_qty=0.5)
    live_state.save_live_state(
        pos, cash=1.0, spot_baseline=None, symbol="BTC/USDT", mark={"equity": 999.0}
    )
    # a later write without mark/symbol keeps the previous ones
    live_state.save_live_state(pos, cash=2.0, spot_baseline=None)
    raw = live_state.load_live_state()
    assert raw["mark"] == {"equity": 999.0}
    assert raw["symbol"] == "BTC/USDT"
    assert raw["cash"] == 2.0
