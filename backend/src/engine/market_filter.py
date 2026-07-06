from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.core.contracts.decision import StageResult
from src.engine.config import FilterConfig


class MarketFilter:
    def __init__(self, config: FilterConfig) -> None:
        self._config = config

    def check(self, context: MarketContext) -> StageResult:
        if context.session not in self._config.allowed_sessions:
            return StageResult(
                passed=False,
                reason="session_not_allowed",
                details={
                    "session": context.session,
                    "allowed": list(self._config.allowed_sessions),
                },
            )

        if context.volatility == "LOW":
            return StageResult(
                passed=False,
                reason="low_volatility",
                details={"volatility": context.volatility},
            )

        if context.atr_pct < self._config.min_atr_pct:
            return StageResult(
                passed=False,
                reason="atr_below_minimum",
                details={"atr_pct": context.atr_pct, "min_atr_pct": self._config.min_atr_pct},
            )

        return StageResult(
            passed=True,
            details={"session": context.session, "atr_pct": context.atr_pct},
        )
