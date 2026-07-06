from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.state import PortfolioState, RiskLimits, RiskState, StateSnapshot


def utc_now() -> datetime:
    return datetime(2026, 7, 6, 10, 0, 0, tzinfo=UTC)


def make_context(
    *,
    session: Literal["ASIA", "EUROPE", "US", "OVERLAP"] = "EUROPE",
    volatility: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL",
    atr_pct: float = 0.5,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    current_price: float = 67000.0,
) -> MarketContext:
    return MarketContext(
        symbol=symbol,
        timeframe=timeframe,
        current_price=current_price,
        trend="UP",
        volatility=volatility,
        atr=current_price * atr_pct / 100,
        atr_pct=atr_pct,
        session=session,
        event_time=utc_now(),
    )


def make_snapshot(
    *,
    drawdown_pct: float = 1.0,
    open_positions: int = 0,
    exposure_pct: float = 10.0,
    signals_today: int = 0,
    snapshot_id: str = "snap_test_001",
) -> StateSnapshot:
    now = utc_now()
    limits = RiskLimits(
        max_daily_drawdown_pct=5.0,
        max_open_positions=3,
        max_exposure_pct=50.0,
    )
    portfolio = PortfolioState(
        portfolio_id="portfolio_test",
        mode="validation",
        cash=10000.0,
        equity=10000.0,
        open_positions=(),
        version=1,
        as_of_event_time=now,
        as_of_processing_time=now,
    )
    risk = RiskState(
        risk_state_id="risk_test_001",
        portfolio_id="portfolio_test",
        daily_drawdown_pct=drawdown_pct,
        open_exposure_pct=exposure_pct,
        signals_today=signals_today,
        limits=limits,
        version=1,
        as_of_event_time=now,
    )
    if open_positions > 0:
        # keep tuple empty for count test via separate fixture if needed
        pass
    return StateSnapshot(
        snapshot_id=snapshot_id,
        portfolio=portfolio,
        risk=risk,
        version=1,
        created_at=now,
    )


def make_snapshot_with_open_positions(count: int) -> StateSnapshot:
    now = utc_now()
    from src.core.contracts.state import PositionState

    positions = tuple(
        PositionState(
            position_id=f"pos_{i}",
            symbol="BTC/USDT",
            side="LONG",
            quantity=0.1,
            entry_price=65000.0,
            entry_time=now,
        )
        for i in range(count)
    )
    limits = RiskLimits(
        max_daily_drawdown_pct=5.0,
        max_open_positions=3,
        max_exposure_pct=50.0,
    )
    portfolio = PortfolioState(
        portfolio_id="portfolio_test",
        mode="validation",
        cash=10000.0,
        equity=10000.0,
        open_positions=positions,
        version=1,
        as_of_event_time=now,
        as_of_processing_time=now,
    )
    risk = RiskState(
        risk_state_id="risk_test_001",
        portfolio_id="portfolio_test",
        daily_drawdown_pct=1.0,
        open_exposure_pct=10.0,
        limits=limits,
        version=1,
        as_of_event_time=now,
    )
    return StateSnapshot(
        snapshot_id="snap_test_positions",
        portfolio=portfolio,
        risk=risk,
        version=1,
        created_at=now,
    )
