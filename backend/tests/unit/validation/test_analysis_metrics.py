from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import (
    DecisionEventType,
    ExecutionEventType,
    MarketEventType,
    build_envelope,
)
from src.validation.metrics import (
    classify_regime,
    compute_diagnostics,
    compute_monthly_breakdown,
    compute_optimization_score,
    compute_outcome_metrics,
    compute_regime_breakdown,
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
    assert "optimization_score" in outcome
    assert len(outcome["monthly_breakdown"]) == 1


def test_optimization_score_caps_low_trade_count() -> None:
    outcome = {
        "return_pct": 8.0,
        "sharpe_ratio": 1.5,
        "win_rate": 0.7,
        "profit_factor": 2.0,
        "max_drawdown_pct": 2.0,
        "total_trades": 5,
    }
    assert compute_optimization_score(outcome) <= -50.0


def test_classify_regime_combines_trend_and_volatility() -> None:
    assert classify_regime({"trend": "UP", "volatility": "HIGH"}) == "UP_HIGH"
    assert classify_regime({"trend": "SIDEWAYS", "volatility": "LOW"}) == "SIDEWAYS_LOW"
    assert classify_regime({}) == "UNKNOWN_UNKNOWN"


def _cycle_events(
    *,
    correlation_id: str,
    event_time: datetime,
    position_id: str,
    pnl: float,
    trend: str,
    volatility: str,
    confidence: float,
    exit_reason: str = "take_profit",
) -> list[object]:
    """One entry cycle (context + decision + open) plus its close on a later bar."""
    common = dict(
        event_family=EventFamily.MARKET,
        event_time=event_time,
        processing_time=event_time,
        correlation_id=correlation_id,
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
    )
    context_event = build_envelope(
        **{**common, "event_family": EventFamily.MARKET},
        event_type=MarketEventType.MARKET_CONTEXT_DERIVED,
        payload={"trend": trend, "volatility": volatility},
    )
    decision_event = build_envelope(
        **{**common, "event_family": EventFamily.DECISION},
        event_type=DecisionEventType.DECISION_MADE,
        payload={"result": "approved", "confidence": confidence},
    )
    open_event = build_envelope(
        **{**common, "event_family": EventFamily.EXECUTION},
        event_type=ExecutionEventType.POSITION_OPENED,
        payload={"position_id": position_id},
    )
    close_event = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=event_time,
        processing_time=event_time,
        correlation_id=f"exit_{correlation_id}",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "position_id": position_id,
            "pnl": pnl,
            "exit_reason": exit_reason,
            "side": "LONG",
            "fill_id": f"f_{position_id}",
        },
    )
    return [context_event, decision_event, open_event, close_event]


def test_regime_breakdown_attributes_trades_to_entry_regime_not_exit_cycle() -> None:
    events = _cycle_events(
        correlation_id="c_entry_1",
        event_time=datetime(2026, 6, 10, 8, tzinfo=UTC),
        position_id="pos_1",
        pnl=-30.0,
        trend="UP",
        volatility="HIGH",
        confidence=0.65,
    ) + _cycle_events(
        correlation_id="c_entry_2",
        event_time=datetime(2026, 6, 11, 8, tzinfo=UTC),
        position_id="pos_2",
        pnl=90.0,
        trend="UP",
        volatility="HIGH",
        confidence=0.85,
    )
    breakdown = compute_regime_breakdown(events)
    assert breakdown["by_regime"]["UP_HIGH"]["trades"] == 2
    assert breakdown["by_regime"]["UP_HIGH"]["pnl"] == pytest.approx(60.0)
    assert breakdown["by_confidence_band"]["0.60-0.69"]["pnl"] == pytest.approx(-30.0)
    assert breakdown["by_confidence_band"]["0.80-1.00"]["pnl"] == pytest.approx(90.0)
    assert breakdown["unattributed_trades"] == 0


def test_regime_breakdown_counts_trades_with_no_entry_context_as_unattributed() -> None:
    orphan_close = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=datetime(2026, 6, 10, 8, tzinfo=UTC),
        processing_time=datetime(2026, 6, 10, 8, tzinfo=UTC),
        correlation_id="exit_only",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "position_id": "pos_orphan",
            "pnl": 10.0,
            "exit_reason": "timeout",
            "side": "LONG",
        },
    )
    breakdown = compute_regime_breakdown([orphan_close])
    assert breakdown["unattributed_trades"] == 1
    assert breakdown["by_regime"] == {}


def test_outcome_metrics_includes_regime_analysis() -> None:
    events = _cycle_events(
        correlation_id="c_entry_1",
        event_time=datetime(2026, 6, 10, 8, tzinfo=UTC),
        position_id="pos_1",
        pnl=100.0,
        trend="DOWN",
        volatility="NORMAL",
        confidence=0.72,
    )
    outcome = compute_outcome_metrics(events, initial_capital=10_000.0)
    assert "regime_analysis" in outcome
    assert outcome["regime_analysis"]["by_regime"]["DOWN_NORMAL"]["trades"] == 1
