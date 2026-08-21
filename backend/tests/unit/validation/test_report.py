from __future__ import annotations

from datetime import UTC, datetime

from src.validation.harness import ValidationConfig, ValidationResult
from src.validation.report import format_report


def _result(outcome_metrics: dict, engine_metrics: dict | None = None) -> ValidationResult:
    return ValidationResult(
        run_id="run_test",
        config=ValidationConfig(
            symbol="BTC/USDT",
            timeframe="1h",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        engine_metrics=engine_metrics or {},
        outcome_metrics=outcome_metrics,
    )


def test_format_report_includes_failure_analysis_section() -> None:
    outcome = {
        "total_trades": 4,
        "win_rate": 0.25,
        "profit_factor": 0.5,
        "max_drawdown": 100.0,
        "sharpe_ratio": -0.2,
        "total_pnl": -60.0,
        "failure_summary": {
            "total_losses": 3,
            "loss_share_by_regime": {"UP_HIGH": 0.6667, "SIDEWAYS_NORMAL": 0.3333},
            "low_confidence_loss_share": 0.5,
            "avg_win": 40.0,
            "avg_loss": -30.0,
            "unattributed_trades": 0,
        },
    }
    report = format_report(_result(outcome))
    assert "=== Failure Analysis ===" in report
    assert "67% occurred during UP_HIGH regime" in report
    assert "33% occurred during SIDEWAYS_NORMAL regime" in report
    assert "50% of losses came from low-confidence signals" in report
    assert "Average loss: -30.00" in report
    assert "Average win: 40.00" in report


def test_format_report_handles_no_losses() -> None:
    report = format_report(_result({"failure_summary": {"total_losses": 0}}))
    assert "No losing trades to analyze." in report


def test_format_report_notes_unattributed_trades() -> None:
    outcome = {
        "failure_summary": {
            "total_losses": 1,
            "loss_share_by_regime": {"UP_HIGH": 1.0},
            "low_confidence_loss_share": 0.0,
            "avg_win": 0.0,
            "avg_loss": -10.0,
            "unattributed_trades": 2,
        }
    }
    report = format_report(_result(outcome))
    assert "2 trades could not be attributed to an entry regime" in report
