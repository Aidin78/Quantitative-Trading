from __future__ import annotations

import uuid
from datetime import datetime

from src.core.contracts.context import MarketContext
from src.core.contracts.decision import (
    AggregationResult,
    Decision,
    DecisionLog,
    DecisionResult,
)
from src.core.contracts.rationale import RiskVerdict
from src.core.contracts.signal import StrategySignal
from src.core.contracts.state import StateSnapshot
from src.engine.aggregator import Aggregator
from src.engine.config import EngineConfig, load_engine_config
from src.engine.final_signal_builder import FinalSignalBuilder
from src.engine.market_filter import MarketFilter
from src.engine.models import AggregatorFailure, AggregatorSuccess
from src.engine.risk_manager import RiskManager


def _skipped_risk_verdict(snapshot: StateSnapshot) -> RiskVerdict:
    return RiskVerdict(
        passed=True,
        checks=(),
        state_snapshot_id=snapshot.snapshot_id,
        risk_state_version=snapshot.risk.version,
    )


def _skipped_aggregation(method: str) -> AggregationResult:
    return AggregationResult(method=method, side="HOLD", confidence=0.0, weights={}, dissent=())


class DecisionEngine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        cfg = config or load_engine_config()
        self._config = cfg
        self._market_filter = MarketFilter(cfg.filter)
        self._aggregator = Aggregator(cfg.aggregation)
        self._risk_manager = RiskManager(cfg.risk)
        self._signal_builder = FinalSignalBuilder()

    @property
    def config(self) -> EngineConfig:
        return self._config

    def process(
        self,
        signals: list[StrategySignal],
        context: MarketContext,
        snapshot: StateSnapshot,
        *,
        correlation_id: str,
        event_time: datetime,
        decision_time: datetime,
        revision_id: str | None = None,
        experiment_id: str | None = None,
    ) -> Decision:
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        method = self._config.aggregation.method
        signal_tuple = tuple(signals)

        market_result = self._market_filter.check(context)
        if not market_result.passed:
            log = DecisionLog(
                market_filter=market_result,
                provider_signals=signal_tuple,
                aggregation=_skipped_aggregation(method),
                risk_check=_skipped_risk_verdict(snapshot),
                state_snapshot_id=snapshot.snapshot_id,
                portfolio_version=snapshot.portfolio.version,
                risk_state_version=snapshot.risk.version,
            )
            return Decision(
                decision_id=decision_id,
                result=DecisionResult(
                    value="rejected",
                    rejection_reason=market_result.reason,
                    rejection_stage="market_filter",
                ),
                decision_log=log,
                correlation_id=correlation_id,
                event_time=event_time,
                decision_time=decision_time,
                revision_id=revision_id,
                experiment_id=experiment_id,
            )

        agg_outcome = self._aggregator.combine(signals)
        if isinstance(agg_outcome, AggregatorFailure):
            aggregation = AggregationResult(
                method=method,
                side="HOLD",
                confidence=0.0,
                weights={},
                dissent=tuple(s.provider_id for s in signals if s.side != "HOLD"),
            )
            log = DecisionLog(
                market_filter=market_result,
                provider_signals=signal_tuple,
                aggregation=aggregation,
                risk_check=_skipped_risk_verdict(snapshot),
                state_snapshot_id=snapshot.snapshot_id,
                portfolio_version=snapshot.portfolio.version,
                risk_state_version=snapshot.risk.version,
            )
            return Decision(
                decision_id=decision_id,
                result=DecisionResult(
                    value="rejected",
                    rejection_reason=agg_outcome.reason,
                    rejection_stage="aggregator",
                ),
                decision_log=log,
                correlation_id=correlation_id,
                event_time=event_time,
                decision_time=decision_time,
                revision_id=revision_id,
                experiment_id=experiment_id,
            )

        aggregated: AggregatorSuccess = agg_outcome
        aggregation = AggregationResult(
            method=method,
            side=aggregated.side,
            confidence=aggregated.confidence,
            weights=aggregated.weights,
            dissent=aggregated.dissent,
        )

        risk_verdict = self._risk_manager.evaluate(aggregated, snapshot)
        if not risk_verdict.passed:
            failed = next(c for c in risk_verdict.checks if not c.passed)
            log = DecisionLog(
                market_filter=market_result,
                provider_signals=signal_tuple,
                aggregation=aggregation,
                risk_check=risk_verdict,
                state_snapshot_id=snapshot.snapshot_id,
                portfolio_version=snapshot.portfolio.version,
                risk_state_version=snapshot.risk.version,
            )
            return Decision(
                decision_id=decision_id,
                result=DecisionResult(
                    value="rejected",
                    rejection_reason=failed.check_name,
                    rejection_stage="risk_manager",
                ),
                decision_log=log,
                correlation_id=correlation_id,
                event_time=event_time,
                decision_time=decision_time,
                revision_id=revision_id,
                experiment_id=experiment_id,
            )

        final_signal = self._signal_builder.build(
            aggregated,
            signals,
            context,
            snapshot,
            decision_time=decision_time,
            revision_id=revision_id,
        )
        risk_verdict = self._risk_manager.finalize_verdict(risk_verdict, final_signal, snapshot)
        if not risk_verdict.passed:
            failed = next(c for c in risk_verdict.checks if not c.passed)
            log = DecisionLog(
                market_filter=market_result,
                provider_signals=signal_tuple,
                aggregation=aggregation,
                risk_check=risk_verdict,
                state_snapshot_id=snapshot.snapshot_id,
                portfolio_version=snapshot.portfolio.version,
                risk_state_version=snapshot.risk.version,
            )
            return Decision(
                decision_id=decision_id,
                result=DecisionResult(
                    value="rejected",
                    rejection_reason=failed.check_name,
                    rejection_stage="risk_manager",
                ),
                decision_log=log,
                correlation_id=correlation_id,
                event_time=event_time,
                decision_time=decision_time,
                revision_id=revision_id,
                experiment_id=experiment_id,
            )

        log = DecisionLog(
            market_filter=market_result,
            provider_signals=signal_tuple,
            aggregation=aggregation,
            risk_check=risk_verdict,
            state_snapshot_id=snapshot.snapshot_id,
            portfolio_version=snapshot.portfolio.version,
            risk_state_version=snapshot.risk.version,
        )
        return Decision(
            decision_id=decision_id,
            result=DecisionResult(value="approved"),
            final_signal=final_signal,
            decision_log=log,
            correlation_id=correlation_id,
            event_time=event_time,
            decision_time=decision_time,
            revision_id=revision_id,
            experiment_id=experiment_id,
        )
