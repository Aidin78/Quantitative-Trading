from __future__ import annotations

from src.validation.lookback import compute_min_lookback_bars


def test_min_lookback_covers_macd() -> None:
    # macd slow 26 + signal 9 => 35, plus 1 buffer => 36
    assert compute_min_lookback_bars() >= 36
