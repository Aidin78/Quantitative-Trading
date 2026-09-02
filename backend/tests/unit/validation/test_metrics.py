from __future__ import annotations

import pytest

from src.core.contracts.event import EventFamily
from src.runtime.models import CycleResult
from src.validation.metrics import (
    EngineMetricsAccumulator,
    compute_engine_metrics,
    compute_outcome_metrics,
)
from tests.mocks.fixtures import make_context, make_snapshot, utc_now


def _minimal_cycle(*, approved: bool = True) -> CycleResult:
    from src.core.contracts.decision import (
        AggregationResult,
        Decision,
        DecisionLog,
        DecisionResult,
        StageResult,
    )
    from src.core.contracts.features import FeatureSet
    from src.core.contracts.rationale import RiskVerdict

    now = utc_now()
    snapshot = make_snapshot()
    log = DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(),
        aggregation=AggregationResult(method="majority", side="BUY", confidence=0.8),
        risk_check=RiskVerdict(
            passed=True,
            checks=(),
            state_snapshot_id=snapshot.snapshot_id,
            risk_state_version=1,
        ),
        state_snapshot_id=snapshot.snapshot_id,
        portfolio_version=1,
        risk_state_version=1,
    )
    decision = Decision(
        decision_id="d1",
        result=DecisionResult(
            value="approved" if approved else "rejected", rejection_reason="low_confidence"
        ),
        decision_log=log,
        correlation_id="c1",
        event_time=now,
        decision_time=now,
    )
    fs = FeatureSet(
        feature_set_id="fs1",
        symbol="BTC/USDT",
        timeframe="1h",
        event_time=now,
        processing_time=now,
        feature_version="v1",
        config_hash="abc",
        close=67000.0,
        indicators={},
        flags={},
    )
    return CycleResult(
        correlation_id="c1",
        feature_set=fs,
        context=make_context(),
        snapshot=snapshot,
        signals=(),
        decision=decision,
        events=(),
    )


def test_approval_rate() -> None:
    cycles = [_minimal_cycle(approved=True), _minimal_cycle(approved=False)]
    metrics = compute_engine_metrics(cycles, [])
    assert metrics["approval_rate"] == 0.5
    assert metrics["approved"] == 1
    assert metrics["rejected"] == 1


def test_engine_metrics_accumulator_matches_batch() -> None:
    cycles = [_minimal_cycle(approved=True), _minimal_cycle(approved=False)]
    acc = EngineMetricsAccumulator()
    for cycle in cycles:
        acc.observe(cycle)
    assert acc.finalize([]) == compute_engine_metrics(cycles, [])


def test_outcome_metrics_from_closed_positions() -> None:
    from src.events.envelopes import ExecutionEventType, build_envelope

    now = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": 100.0,
                "position_id": "p1",
                "exit_reason": "take_profit",
                "fill_id": "f1",
            },
        ),
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c2",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": -50.0,
                "position_id": "p2",
                "exit_reason": "stop_loss",
                "fill_id": "f2",
            },
        ),
    ]
    om = compute_outcome_metrics(events, initial_capital=10_000.0)
    assert om["total_trades"] == 2
    assert om["win_rate"] == 0.5
    assert om["total_pnl"] == 50.0
    assert om["initial_capital"] == 10_000.0
    assert om["ending_equity"] == 10_050.0
    assert om["return_pct"] == pytest.approx(0.5)
    assert om["equity_curve"][0] == 10_000.0
    assert om["positions_closed"] == 2


def test_outcome_metrics_daily_sharpe_sortino() -> None:
    from datetime import timedelta

    from src.events.envelopes import ExecutionEventType, build_envelope

    base = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=base,
            processing_time=base,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": 100.0,
                "position_id": "p1",
                "exit_reason": "take_profit",
                "fill_id": "f1",
            },
        ),
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=base + timedelta(days=1),
            processing_time=base + timedelta(days=1),
            correlation_id="c2",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": -30.0,
                "position_id": "p2",
                "exit_reason": "stop_loss",
                "fill_id": "f2",
            },
        ),
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=base + timedelta(days=2),
            processing_time=base + timedelta(days=2),
            correlation_id="c3",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": 50.0,
                "position_id": "p3",
                "exit_reason": "take_profit",
                "fill_id": "f3",
            },
        ),
    ]
    om = compute_outcome_metrics(events, initial_capital=10_000.0)
    assert om["daily_return_count"] == 3
    assert om["sharpe_ratio"] != 0.0
    assert om["sortino_ratio"] != 0.0
    assert "trade_sharpe_ratio" in om


def test_mtm_drawdown_captures_unrealized_swing() -> None:
    """A position held straight through a crash: trade-realized DD is ~0,
    mark-to-market DD reflects the real peak-to-trough."""
    from datetime import timedelta

    from src.events.envelopes import (
        ExecutionEventType,
        MarketEventType,
        build_envelope,
    )

    base = utc_now()

    def candle(day: int, close: float):
        t = base + timedelta(days=day)
        return build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=t,
            processing_time=t,
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0},
        )

    opened = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_OPENED,
        event_time=base,
        processing_time=base,
        correlation_id="c0",
        symbol="BTC/USDT",
        timeframe="1d",
        mode="validation",
        payload={
            "position_id": "p1",
            "position": {"quantity": 1.0, "entry_price": 100.0, "side": "LONG"},
        },
    )
    closed = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=base + timedelta(days=4),
        processing_time=base + timedelta(days=4),
        correlation_id="c4",
        symbol="BTC/USDT",
        timeframe="1d",
        mode="validation",
        payload={"pnl": 5.0, "position_id": "p1", "exit_reason": "signal", "side": "LONG"},
    )
    # 100 -> 50 (-50%) -> 105 close
    events = [
        candle(0, 100.0),
        opened,
        candle(1, 80.0),
        candle(2, 50.0),
        candle(3, 90.0),
        candle(4, 105.0),
        closed,
    ]
    om = compute_outcome_metrics(events, initial_capital=100.0)
    assert om["max_drawdown_pct"] == pytest.approx(0.0, abs=1e-9)  # trade-realized: flat then +5
    assert om["mtm_max_drawdown_pct"] == pytest.approx(50.0, rel=1e-6)
    assert om["mtm_return_pct"] == pytest.approx(5.0, rel=1e-6)


def test_mtm_handles_overlapping_positions() -> None:
    """Two positions open at once: the equity curve must reflect both, not just
    whichever opened last (a scalar tracker double-debits cash and blows up)."""
    from datetime import timedelta

    from src.events.envelopes import ExecutionEventType, MarketEventType, build_envelope

    base = utc_now()

    def candle(day: int, close: float):
        t = base + timedelta(days=day)
        return build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=t,
            processing_time=t,
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0},
        )

    def opened(day: int, pid: str, entry: float):
        t = base + timedelta(days=day)
        return build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_OPENED,
            event_time=t,
            processing_time=t,
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={
                "position_id": pid,
                "position": {"quantity": 1.0, "entry_price": entry, "side": "LONG"},
            },
        )

    def closed(day: int, pid: str, pnl: float):
        t = base + timedelta(days=day)
        return build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=t,
            processing_time=t,
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={"pnl": pnl, "position_id": pid, "exit_reason": "signal", "side": "LONG"},
        )

    events = [
        candle(0, 100.0),
        opened(0, "p1", 100.0),
        candle(1, 110.0),
        opened(1, "p2", 110.0),  # second position, both now open
        candle(2, 120.0),  # p1 +20, p2 +10 => equity 100 + 30
        closed(2, "p1", 20.0),
        candle(3, 120.0),  # only p2 open, still +10 unrealised
        closed(3, "p2", 10.0),
    ]
    om = compute_outcome_metrics(events, initial_capital=100.0)
    assert om["mtm_equity_curve"][-1] == pytest.approx(130.0, rel=1e-6)
    assert om["mtm_return_pct"] == pytest.approx(30.0, rel=1e-6)
    assert om["mtm_max_drawdown_pct"] == pytest.approx(0.0, abs=1e-6)


def test_equity_timeline_tracks_strategy_and_buy_and_hold() -> None:
    """The dated timeline must carry both the marked-to-market strategy curve and
    a buy & hold benchmark rebased to the same starting capital."""
    from datetime import timedelta

    from src.events.envelopes import ExecutionEventType, MarketEventType, build_envelope

    base = utc_now()

    def candle(day: int, close: float):
        t = base + timedelta(days=day)
        return build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=t,
            processing_time=t,
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0},
        )

    opened = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_OPENED,
        event_time=base,
        processing_time=base,
        correlation_id="c0",
        symbol="BTC/USDT",
        timeframe="1d",
        mode="validation",
        payload={
            "position_id": "p1",
            "position": {"quantity": 1.0, "entry_price": 100.0, "side": "LONG"},
        },
    )
    closed = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=base + timedelta(days=2),
        processing_time=base + timedelta(days=2),
        correlation_id="c2",
        symbol="BTC/USDT",
        timeframe="1d",
        mode="validation",
        payload={"pnl": 50.0, "position_id": "p1", "exit_reason": "signal", "side": "LONG"},
    )
    # price 100 -> 150 (+50%); strategy holds one unit the whole way
    events = [candle(0, 100.0), opened, candle(1, 125.0), candle(2, 150.0), closed]

    om = compute_outcome_metrics(events, initial_capital=100.0)
    timeline = om["equity_timeline"]
    assert [row["date"] for row in timeline["points"]] == [
        (base + timedelta(days=d)).date().isoformat() for d in range(3)
    ]
    assert timeline["points"][0]["benchmark"] == pytest.approx(100.0)
    assert timeline["points"][-1]["benchmark"] == pytest.approx(150.0)
    assert timeline["points"][-1]["strategy"] == pytest.approx(150.0)
    assert timeline["benchmark_return_pct"] == pytest.approx(50.0, rel=1e-6)


def test_equity_timeline_downsamples_long_runs() -> None:
    from datetime import timedelta

    from src.events.envelopes import MarketEventType, build_envelope

    base = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=base + timedelta(days=day),
            processing_time=base + timedelta(days=day),
            correlation_id=f"c{day}",
            symbol="BTC/USDT",
            timeframe="1d",
            mode="validation",
            payload={
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0 + day,
                "volume": 1.0,
            },
        )
        for day in range(1200)
    ]
    om = compute_outcome_metrics(events, initial_capital=10_000.0)
    points = om["equity_timeline"]["points"]
    assert len(points) <= 401
    # the final bar is always kept so the endpoint value is exact
    assert points[-1]["date"] == (base + timedelta(days=1199)).date().isoformat()


def test_mtm_series_absent_without_candles() -> None:
    from src.events.envelopes import ExecutionEventType, build_envelope

    now = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={"pnl": 10.0, "position_id": "p1", "exit_reason": "tp"},
        )
    ]
    om = compute_outcome_metrics(events, initial_capital=10_000.0)
    assert "mtm_max_drawdown_pct" not in om
