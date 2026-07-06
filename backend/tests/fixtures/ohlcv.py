from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd


def make_sample_ohlcv(*, bars: int = 100, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[dict[str, object]] = []
    price = 67000.0
    for i in range(bars):
        ts = start + timedelta(hours=i)
        change = float(rng.normal(0, 120))
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + abs(float(rng.normal(0, 40)))
        low_p = min(open_p, close_p) - abs(float(rng.normal(0, 40)))
        vol = float(abs(rng.normal(0, 100)) + 50)
        rows.append(
            {
                "timestamp": ts,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": round(vol, 2),
            }
        )
        price = close_p
    return pd.DataFrame(rows)
