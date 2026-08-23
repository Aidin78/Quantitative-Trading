"""Shared core for the signal-research pipeline: data loading and forward-looking targets.

Look-ahead rule (load-bearing — a prior look-ahead mistake in this exact research
motivated this module): every predictive claim in this package must compare a
backward-looking signal, known at bar ``t``, against a target computed with
``shift(-h)`` from bar ``t``. Never use a signal or target derived from the full
length or final direction of a "run" (a contiguous stretch where some label stays
constant) — that end point depends on bars after ``t`` and leaks the future,
even though it looks like an innocuous groupby. Every ``fwd_*`` column here is
built from ``shift(-h)`` for exactly this reason.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from src.data.csv_provider import CsvDataProvider
from src.data.market_cache import get_or_download_csv

DEFAULT_HORIZONS: tuple[int, ...] = (4, 8, 14, 24)


def resolve_csv_fixture(path: str | None) -> Path:
    """Resolve a local CSV path, falling back to the repo's bundled fixtures."""
    if path:
        return Path(path)
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [
        backend_root / "tests" / "fixtures" / "sample_btc_1h.csv",
        backend_root / "tests" / "fixtures" / "ohlcv_btc_1h.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No CSV fixture found")


async def load_ohlcv(
    *,
    source: Literal["exchange", "csv"],
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    csv_path: str | None = None,
    exchange_id: str = "binance",
) -> pd.DataFrame:
    """Load raw OHLCV for the research pipeline via the platform's own CSV path.

    Reuses ``CsvDataProvider``/``get_or_download_csv`` — the same loading code
    ``run_validation_job`` uses — so research data never drifts from what a real
    backtest sees.
    """
    if source == "csv":
        path = resolve_csv_fixture(csv_path)
    else:
        path = await get_or_download_csv(
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
    provider = CsvDataProvider(path, symbol=symbol, timeframe=timeframe)
    return provider.get_ohlcv(symbol, timeframe, start, end)


def compute_forward_targets(
    df: pd.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Attach forward-only target columns for each horizon in ``horizons``.

    For each ``h``: ``fwd_ret_h`` (signed % return), ``fwd_absret_h``
    (magnitude), ``fwd_maxrange_h`` (highest high minus lowest low over the
    next ``h`` bars, as % of the current close — captures a breakout even if
    price round-trips back by bar ``t+h``). All three are computed with
    ``shift(-h)`` / a reversed rolling window over *future* bars only.
    """
    out = df.copy()
    close = out["close"]
    for h in horizons:
        out[f"fwd_ret_{h}"] = (close.shift(-h) / close - 1) * 100
        out[f"fwd_absret_{h}"] = out[f"fwd_ret_{h}"].abs()
        fwd_high = out["high"].iloc[::-1].rolling(h).max().iloc[::-1].shift(-1)
        fwd_low = out["low"].iloc[::-1].rolling(h).min().iloc[::-1].shift(-1)
        out[f"fwd_maxrange_{h}"] = (fwd_high - fwd_low) / close * 100
    return out
