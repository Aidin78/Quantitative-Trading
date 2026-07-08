from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import ExecutionEventType, build_envelope
from src.validation.metrics import (
    compute_diagnostics,
    compute_monthly_breakdown,
    compute_outcome_metrics,
    compute_strategy_score,
)


def _close_event(
    *,
    pnl: float,
    event_time: datetime,
    exit_reason: str = "take_profit",
    side: str = "LONG",
) -> object:
    return build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=event_time,
        processing_time=event_time,
        correlation_id=f"c_{event_time.isoformat()}",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "pnl": pnl,
            "position_id": f"p_{event_time.isoformat()}",
            "exit_reason": exit_reason,
            "side": side,
            "fill_id": f"f_{event_time.isoformat()}",
        },
    )


def test_monthly_breakdown_groups_by_month() -> None:
    events = [
        _close_event(pnl=100.0, event_time=datetime(2026, 6, 10, 10, tzinfo=UTC)),
        _close_event(pnl=-40.0, event_time=datetime(2026, 6, 20, 10, tzinfo=UTC)),
        _close_event(pnl=50.0, event_time=datetime(2026, 7, 5, 10, tzinfo=UTC)),
    ]
    rows = compute_monthly_breakdown(events, initial_capital=10_000.0)
    assert len(rows) == 2
    assert rows[0]["month"] == "2026-06"
    assert rows[0]["pnl"] == pytest.approx(60.0)
    assert rows[0]["return_pct"] == pytest.approx(0.6)
    assert rows[1]["month"] == "2026-07"
    assert rows[1]["start_equity"] == pytest.approx(10_060.0)
    assert rows[1]["end_equity"] == pytest.approx(10_110.0)


def test_diagnostics_buckets_exit_reason_and_side() -> None:
    events = [
        _close_event(
            pnl=-30.0,
            event_time=datetime(2026, 6, 10, 8, tzinfo=UTC),
            exit_reason="stop_loss",
            side="LONG",
        ),
        _close_event(
            pnl=80.0,
            event_time=datetime(2026, 6, 10, 17, tzinfo=UTC),
            exit_reason="take_profit",
            side="SHORT",
        ),
    ]
    diag = compute_diagnostics(events)
    assert diag["by_exit_reason"]["stop_loss"]["pnl"] == pytest.approx(-30.0)
    assert diag["by_exit_reason"]["take_profit"]["trades"] == 1
    assert diag["by_session"]["EUROPE"]["trades"] == 1
    assert diag["by_session"]["US"]["trades"] == 1
    assert diag["by_side"]["LONG"]["pnl"] == pytest.approx(-30.0)
    assert diag["by_side"]["SHORT"]["pnl"] == pytest.approx(80.0)


def test_strategy_score_positive_outcome() -> None:
    outcome = {
        "return_pct": 5.0,
        "sharpe_ratio": 1.0,
        "win_rate": 0.6,
        "profit_factor": 1.5,
        "max_drawdown_pct": 2.0,
    }
    score = compute_strategy_score(outcome)
    assert score > 0


def test_strategy_score_penalizes_drawdown() -> None:
    base = {
        "return_pct": 5.0,
        "sharpe_ratio": 1.0,
        "win_rate": 0.6,
        "profit_factor": 1.5,
        "max_drawdown_pct": 2.0,
    }
    worse = {**base, "max_drawdown_pct": 10.0}
    assert compute_strategy_score(worse) < compute_strategy_score(base)


def test_outcome_metrics_includes_analysis_fields() -> None:
    events = [
        _close_event(pnl=100.0, event_time=datetime(2026, 6, 10, 10, tzinfo=UTC)),
    ]
    outcome = compute_outcome_metrics(events, initial_capital=10_000.0)
    assert "monthly_breakdown" in outcome
    assert "diagnostics" in outcome
    assert "score" in outcome
    assert len(outcome["monthly_breakdown"]) == 1
