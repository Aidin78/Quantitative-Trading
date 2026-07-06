from __future__ import annotations

from src.core.contracts.rationale import RiskCheckResult, RiskVerdict
from src.core.contracts.signal import FinalSignal
from src.core.contracts.state import StateSnapshot
from src.engine.config import RiskConfig
from src.engine.models import AggregatorSuccess


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self._config = config

    def evaluate(self, aggregated: AggregatorSuccess, snapshot: StateSnapshot) -> RiskVerdict:
        risk = snapshot.risk
        portfolio = snapshot.portfolio
        checks: list[RiskCheckResult] = []

        checks.append(
            RiskCheckResult(
                check_name="daily_drawdown",
                passed=risk.daily_drawdown_pct < self._config.max_daily_drawdown_pct,
                current_value=risk.daily_drawdown_pct,
                threshold=self._config.max_daily_drawdown_pct,
                message="daily drawdown within limit"
                if risk.daily_drawdown_pct < self._config.max_daily_drawdown_pct
                else "daily drawdown limit breached",
            )
        )

        checks.append(
            RiskCheckResult(
                check_name="max_signals_per_day",
                passed=risk.signals_today < self._config.max_signals_per_day,
                current_value=float(risk.signals_today),
                threshold=float(self._config.max_signals_per_day),
                message="signals today within limit"
                if risk.signals_today < self._config.max_signals_per_day
                else "max signals per day reached",
            )
        )

        open_count = len(portfolio.open_positions)
        checks.append(
            RiskCheckResult(
                check_name="max_open_positions",
                passed=open_count < self._config.max_open_positions,
                current_value=float(open_count),
                threshold=float(self._config.max_open_positions),
                message="open positions within limit"
                if open_count < self._config.max_open_positions
                else "max open positions reached",
            )
        )

        checks.append(
            RiskCheckResult(
                check_name="max_exposure",
                passed=risk.open_exposure_pct <= self._config.max_exposure_pct,
                current_value=risk.open_exposure_pct,
                threshold=self._config.max_exposure_pct,
                message="exposure within limit"
                if risk.open_exposure_pct <= self._config.max_exposure_pct
                else "max exposure exceeded",
            )
        )

        checks.append(
            RiskCheckResult(
                check_name="min_confidence",
                passed=aggregated.confidence >= self._config.min_confidence,
                current_value=aggregated.confidence,
                threshold=self._config.min_confidence,
                message="confidence sufficient"
                if aggregated.confidence >= self._config.min_confidence
                else "confidence below minimum",
            )
        )

        passed = all(c.passed for c in checks)
        return RiskVerdict(
            passed=passed,
            checks=tuple(checks),
            state_snapshot_id=snapshot.snapshot_id,
            risk_state_version=risk.version,
        )

    def finalize_verdict(
        self,
        verdict: RiskVerdict,
        final_signal: FinalSignal,
        snapshot: StateSnapshot,
    ) -> RiskVerdict:
        rr_check = RiskCheckResult(
            check_name="min_risk_reward",
            passed=final_signal.risk_reward >= self._config.min_risk_reward,
            current_value=final_signal.risk_reward,
            threshold=self._config.min_risk_reward,
            message="risk reward sufficient"
            if final_signal.risk_reward >= self._config.min_risk_reward
            else "risk reward below minimum",
        )
        checks = verdict.checks + (rr_check,)
        return RiskVerdict(
            passed=verdict.passed and rr_check.passed,
            checks=checks,
            state_snapshot_id=snapshot.snapshot_id,
            risk_state_version=snapshot.risk.version,
        )
