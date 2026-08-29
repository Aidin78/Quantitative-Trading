"""Perp market snapshots for the carry runner.

``PerpSnapshot`` bundles what one cycle needs: spot price, perp mark, the
funding rate for the interval just settled, and the trailing funding used for
the in/out decision.

Two providers:
  - ``HistoricalPerpProvider`` replays cached OHLCV + funding CSVs (for the
    paper runner and tests) — deterministic, no network.
  - ``LivePerpProvider`` polls ccxt (for the live runner).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class PerpSnapshot:
    ts: datetime
    symbol: str
    spot_px: float
    perp_mark_px: float
    funding_rate: float  # settled over the interval ending at ts (0 if none)
    trailing_funding_8h: float  # mean 8h funding over the trailing window, known before ts
    is_funding_time: bool


class HistoricalPerpProvider:
    """Replay a daily spot series + 8h funding history as per-day snapshots.

    The perp mark is approximated by the spot close plus the running basis
    implied by funding (small); good enough for a paper backtest whose point
    is to validate the runner/position-manager chain, not to model basis P&L.
    """

    def __init__(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
        funding: pd.DataFrame,
        *,
        trail_prints: int = 3,
    ) -> None:
        self.symbol = symbol
        px = ohlcv.copy()
        px["day"] = pd.to_datetime(px["timestamp"], utc=True).dt.floor("D")
        self._close = px.set_index("day")["close"]

        f = funding.sort_values("timestamp").copy()
        f["day"] = f["timestamp"].dt.floor("D")
        self._daily_funding = f.groupby("day")["funding_rate"].sum()
        self._trailing = (
            f.set_index("timestamp")["funding_rate"]
            .rolling(f"{trail_prints * 8}h")
            .mean()
            .resample("D")
            .last()
            .shift(1)
        )

    def snapshots(self) -> Iterator[PerpSnapshot]:
        for day, close in self._close.items():
            fr = float(self._daily_funding.get(day, 0.0))
            trail = self._trailing.get(day)
            yield PerpSnapshot(
                ts=day.to_pydatetime(),
                symbol=self.symbol,
                spot_px=float(close),
                perp_mark_px=float(close),
                funding_rate=fr,
                trailing_funding_8h=float(trail) if pd.notna(trail) else 0.0,
                is_funding_time=day in self._daily_funding.index,
            )


class LivePerpProvider:
    """Poll ccxt for a live snapshot. Requires network + a configured exchange."""

    def __init__(self, symbol: str, *, exchange_id: str = "binance", trail_prints: int = 3) -> None:
        self.symbol = symbol
        self.exchange_id = exchange_id
        self.trail_prints = trail_prints

    def _perp_symbol(self) -> str:
        base, quote = self.symbol.split("/")
        return f"{base}/{quote}:{quote}"

    def snapshot(self) -> PerpSnapshot:
        import ccxt

        ex = getattr(ccxt, self.exchange_id)(
            {"options": {"defaultType": "future"}, "timeout": 20000, "enableRateLimit": True}
        )
        perp = self._perp_symbol()
        spot_t = ex.fetch_ticker(self.symbol)
        perp_t = ex.fetch_ticker(perp)
        fr = ex.fetch_funding_rate(perp)
        hist = ex.fetch_funding_rate_history(perp, limit=self.trail_prints)
        trail = (
            sum(h["fundingRate"] for h in hist) / len(hist) if hist else float(fr["fundingRate"])
        )
        now = datetime.now().astimezone()
        return PerpSnapshot(
            ts=now,
            symbol=self.symbol,
            spot_px=float(spot_t["last"]),
            perp_mark_px=float(perp_t.get("last") or fr.get("markPrice") or spot_t["last"]),
            funding_rate=float(fr["fundingRate"]),
            trailing_funding_8h=float(trail),
            is_funding_time=True,
        )
