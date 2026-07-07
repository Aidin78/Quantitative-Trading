from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.api.services.live_runner import build_live_stack
from src.data.csv_provider import CsvDataProvider


@pytest.mark.asyncio
async def test_live_paper_cycle_with_csv_as_live_provider() -> None:
    """Paper cycle using CSV data wired through the live stack (no network)."""
    csv = Path(__file__).resolve().parents[1] / "fixtures" / "sample_btc_1h.csv"
    if not csv.exists():
        csv = Path(__file__).resolve().parents[1] / "fixtures" / "ohlcv_btc_1h.csv"
    provider = CsvDataProvider(csv, symbol="BTC/USDT", timeframe="1h")

    with patch("src.api.services.live_runner.LiveProvider", return_value=provider):
        stack = await build_live_stack("paper", persist_db=False, prefer_redis=False)
        result = await stack.runtime.run_cycle("BTC/USDT", "1h", correlation_id="live_test_cycle")
    assert result.decision is not None
    assert result.correlation_id == "live_test_cycle"
    event_types = [e.event_type for e in result.events]
    assert "DecisionMade" in event_types
