from __future__ import annotations

from src.validation.lookback import compute_min_lookback_bars


def test_min_lookback_covers_macd() -> None:
    # macd histogram_slope: slow 26 + signal 9 + 1 => 36, plus 1 buffer => 37
    assert compute_min_lookback_bars() >= 37
