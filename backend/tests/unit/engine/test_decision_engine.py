from __future__ import annotations

import pytest

from src.engine.config import load_engine_config
from src.engine.decision_engine import DecisionEngine
from tests.mocks.fixtures import make_context, make_snapshot, utc_now
from tests.mocks.mock_signals import conflict_signals, consensus_buy_signals, make_signal


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine(load_engine_config())


@pytest.fixture
def times():
    now = utc_now()
    return {"event_time": now, "decision_time": now}


def test_consensus_two_providers_buy_approved(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(),
        correlation_id="cycle_consensus",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert decision.is_approved
    assert decision.final_signal is not None
    assert decision.final_signal.side == "BUY"
    assert len(decision.decision_log.provider_signals) == 2
    assert decision.decision_log.risk_check.passed


def test_conflict_buy_vs_sell_rejected_at_aggregator(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        conflict_signals(times["event_time"]),
        make_context(),
        make_snapshot(),
        correlation_id="cycle_conflict",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "aggregator"
    assert decision.result.rejection_reason == "provider_conflict"
    assert decision.decision_log.market_filter.passed


def test_risk_drawdown_exceeded_rejected(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(drawdown_pct=6.0),
        correlation_id="cycle_risk",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "risk_manager"
    assert decision.result.rejection_reason == "daily_drawdown"
    assert not decision.decision_log.risk_check.passed


def test_market_filter_low_volatility_rejected(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(volatility="LOW"),
        make_snapshot(),
        correlation_id="cycle_filter_vol",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "market_filter"
    assert decision.result.rejection_reason == "low_volatility"


def test_market_filter_session_not_allowed(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(session="ASIA"),
        make_snapshot(),
        correlation_id="cycle_filter_session",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "market_filter"
    assert decision.result.rejection_reason == "session_not_allowed"


def test_decision_log_complete_on_every_path(engine: DecisionEngine, times: dict) -> None:
    scenarios = [
        engine.process(
            consensus_buy_signals(times["event_time"]),
            make_context(),
            make_snapshot(),
            correlation_id="log_ok",
            event_time=times["event_time"],
            decision_time=times["decision_time"],
        ),
        engine.process(
            conflict_signals(times["event_time"]),
            make_context(),
            make_snapshot(),
            correlation_id="log_conflict",
            event_time=times["event_time"],
            decision_time=times["decision_time"],
        ),
    ]
    for decision in scenarios:
        log = decision.decision_log
        assert log.state_snapshot_id == "snap_test_001"
        assert log.portfolio_version == 1
        assert log.risk_state_version == 1
        assert log.market_filter is not None
        assert log.aggregation is not None
        assert log.risk_check is not None
        assert len(log.provider_signals) >= 1


def test_low_confidence_rejected_at_risk(engine: DecisionEngine, times: dict) -> None:
    low_conf = [
        make_signal("ema_crossover", "BUY", 0.5, event_time=times["event_time"]),
        make_signal("rsi_divergence", "BUY", 0.55, event_time=times["event_time"]),
    ]
    decision = engine.process(
        low_conf,
        make_context(),
        make_snapshot(),
        correlation_id="cycle_low_conf",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "risk_manager"
    assert decision.result.rejection_reason == "min_confidence"


def test_max_signals_per_day_rejected(engine: DecisionEngine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(signals_today=10),
        correlation_id="cycle_max_signals",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "risk_manager"
    assert decision.result.rejection_reason == "max_signals_per_day"


def test_min_risk_reward_rejected(engine: DecisionEngine, times: dict) -> None:
    poor_rr = [
        make_signal(
            "ema_crossover",
            "BUY",
            0.78,
            event_time=times["event_time"],
            stop_loss=66500.0,
            take_profit=67100.0,
        ),
        make_signal(
            "rsi_divergence",
            "BUY",
            0.72,
            event_time=times["event_time"],
            stop_loss=66500.0,
            take_profit=67100.0,
        ),
    ]
    decision = engine.process(
        poor_rr,
        make_context(),
        make_snapshot(),
        correlation_id="cycle_low_rr",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_stage == "risk_manager"
    assert decision.result.rejection_reason == "min_risk_reward"
