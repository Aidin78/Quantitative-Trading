from __future__ import annotations

from src.api.services.optimization_service import trial_to_dict
from src.validation.optimizer import TrialResult


def test_trial_to_dict_derives_train_return_from_pnl() -> None:
    trial = TrialResult(
        trial_id="trial_a",
        params={"min_confidence": 0.6},
        train_score=5.0,
        train_outcome={"total_trades": 3, "total_pnl": 250.0, "initial_capital": 10000.0},
    )
    payload = trial_to_dict(trial)
    assert payload["train_return_pct"] == 2.5
    assert payload["test_return_pct"] is None


def test_trial_to_dict_exports_zero_test_return() -> None:
    trial = TrialResult(
        trial_id="trial_b",
        params={"min_confidence": 0.6},
        train_score=1.0,
        train_outcome={"total_trades": 0, "return_pct": 0.0},
        test_score=2.0,
        test_outcome={"total_trades": 0, "return_pct": 0.0},
    )
    payload = trial_to_dict(trial)
    assert payload["test_return_pct"] == 0.0
    assert payload["train_return_pct"] == 0.0


def test_trial_to_dict_ignores_non_finite_return() -> None:
    trial = TrialResult(
        trial_id="trial_c",
        params={"min_confidence": 0.6},
        train_score=1.0,
        train_outcome={"total_trades": 1, "return_pct": float("nan")},
        test_score=2.0,
        test_outcome={"total_trades": 1, "return_pct": float("inf")},
    )
    payload = trial_to_dict(trial)
    assert payload["train_return_pct"] == 0.0
    assert payload["test_return_pct"] == 0.0
