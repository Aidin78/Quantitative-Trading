from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.governance.candidate_evaluator import evaluate_candidate
from src.validation.optimization_scoring import OptimizationResult, TrialResult


def _base_result(**overrides) -> OptimizationResult:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    defaults = dict(
        sweep_id="sweep_test",
        symbol="BTC/USDT",
        timeframe="1h",
        train_start=now,
        train_end=now,
        test_start=now,
        test_end=now,
        holdout_valid=True,
        holdout_outcome={
            "total_trades": 40,
            "regime_analysis": {
                "by_regime": {
                    "UP_HIGH": {"trades": 15},
                    "SIDEWAYS_NORMAL": {"trades": 15},
                    "DOWN_LOW": {"trades": 10},
                }
            },
        },
        best=TrialResult(
            trial_id="trial_1",
            params={},
            train_score=1.0,
            train_outcome={},
            fold_scores=[1.0, 1.1, 0.9],
            fold_std=0.5,
        ),
    )
    defaults.update(overrides)
    return OptimizationResult(**defaults)


def test_evaluate_candidate_accepts_when_all_checks_pass() -> None:
    checks, decision, reason = evaluate_candidate(_base_result())
    assert decision == "accepted"
    assert all(check.passed for check in checks)
    assert reason == "All checks passed."


def test_evaluate_candidate_rejects_on_failed_holdout() -> None:
    result = _base_result(holdout_valid=False)
    checks, decision, reason = evaluate_candidate(result)
    assert decision == "rejected"
    assert "out_of_sample" in reason
    oos_check = next(c for c in checks if c.check_name == "out_of_sample")
    assert oos_check.passed is False


def test_evaluate_candidate_rejects_on_insufficient_sample() -> None:
    result = _base_result(holdout_outcome={"total_trades": 5, "regime_analysis": {}})
    checks, decision, reason = evaluate_candidate(result)
    assert decision == "rejected"
    assert "minimum_sample" in reason


def test_evaluate_candidate_rejects_on_regime_concentration() -> None:
    result = _base_result(
        holdout_outcome={
            "total_trades": 40,
            "regime_analysis": {
                "by_regime": {
                    "UP_HIGH": {"trades": 38},
                    "DOWN_LOW": {"trades": 2},
                }
            },
        }
    )
    checks, decision, reason = evaluate_candidate(result)
    assert decision == "rejected"
    assert "regime_concentration" in reason
    regime_check = next(c for c in checks if c.check_name == "regime_concentration")
    assert regime_check.current_value == pytest.approx(38 / 40)


def test_evaluate_candidate_rejects_on_unstable_folds() -> None:
    result = _base_result(
        best=TrialResult(
            trial_id="trial_unstable",
            params={},
            train_score=1.0,
            train_outcome={},
            fold_scores=[10.0, -20.0, 5.0],
            fold_std=100.0,
        )
    )
    checks, decision, reason = evaluate_candidate(result)
    assert decision == "rejected"
    assert "fold_stability" in reason


def test_evaluate_candidate_treats_missing_fold_data_as_not_evaluated_not_passed() -> None:
    result = _base_result(
        best=TrialResult(trial_id="t", params={}, train_score=1.0, train_outcome={})
    )
    checks, decision, _ = evaluate_candidate(result)
    fold_check = next(c for c in checks if c.check_name == "fold_stability")
    assert fold_check.passed is False
    assert "not_evaluated" in fold_check.detail
    assert decision == "rejected"
