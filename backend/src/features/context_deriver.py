from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from src.core.contracts.context import MarketContext
from src.features.config import ContextConfig


class ContextDeriver:
    def __init__(self, config: ContextConfig) -> None:
        self._config = config

    def derive(
        self,
        *,
        symbol: str,
        timeframe: str,
        close: float,
        indicators: dict[str, float],
        event_time: datetime,
    ) -> MarketContext:
        trend = self._derive_trend(indicators)
        atr, atr_pct = self._derive_atr_metrics(close, indicators)
        volatility = self._derive_volatility(atr_pct)
        session = self._derive_session(event_time)
        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            current_price=close,
            trend=trend,
            volatility=volatility,
            atr=atr,
            atr_pct=atr_pct,
            session=session,
            event_time=event_time,
        )

    def _derive_trend(self, indicators: dict[str, float]) -> Literal["UP", "DOWN", "SIDEWAYS"]:
        cfg = self._config.trend
        if cfg.method == "ema_compare":
            fast = indicators[cfg.fast]
            slow = indicators[cfg.slow]
            if fast > slow:
                return "UP"
            if fast < slow:
                return "DOWN"
            return "SIDEWAYS"
        return "SIDEWAYS"

    def _derive_atr_metrics(
        self, close: float, indicators: dict[str, float]
    ) -> tuple[float, float]:
        cfg = self._config.volatility
        atr = indicators[cfg.atr]
        atr_pct = (atr / close * 100) if close else 0.0
        return atr, round(atr_pct, 4)

    def _derive_volatility(self, atr_pct: float) -> Literal["LOW", "NORMAL", "HIGH"]:
        cfg = self._config.volatility
        if atr_pct < cfg.low:
            return "LOW"
        if atr_pct > cfg.high:
            return "HIGH"
        return "NORMAL"

    def _derive_session(self, event_time: datetime) -> Literal["ASIA", "EUROPE", "US", "OVERLAP"]:
        dt = event_time.astimezone(ZoneInfo(self._config.session.timezone))
        hour = dt.hour
        if 12 <= hour < 16:
            return "OVERLAP"
        if 7 <= hour < 12:
            return "EUROPE"
        if 16 <= hour < 21:
            return "US"
        return "ASIA"
