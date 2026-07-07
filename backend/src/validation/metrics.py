from __future__ import annotations

from collections import Counter

from src.core.contracts.event import EventEnvelope, EventFamily
from src.events.envelopes import DecisionEventType, ExecutionEventType
from src.runtime.models import CycleResult


def compute_engine_metrics(
    cycles: list[CycleResult],
    events: list[EventEnvelope],
) -> dict:
    total = len(cycles)
    approved = sum(1 for c in cycles if c.decision.is_approved)
    rejected = total - approved

    rejection_reasons: Counter[str] = Counter()
    rejection_stages: Counter[str] = Counter()
    provider_hits: Counter[str] = Counter()

    for cycle in cycles:
        if cycle.decision.is_approved and cycle.decision.final_signal:
            for pid in cycle.decision.final_signal.contributing_providers:
                provider_hits[pid] += 1
        elif not cycle.decision.is_approved:
            reason = cycle.decision.result.rejection_reason or "unknown"
            stage = cycle.decision.result.rejection_stage or "unknown"
            rejection_reasons[reason] += 1
            rejection_stages[stage] += 1

    decision_events = [e for e in events if e.event_family == EventFamily.DECISION]
    with_snapshot = sum(
        1
        for e in decision_events
        if e.event_type in (DecisionEventType.DECISION_MADE, DecisionEventType.DECISION_APPROVED)
        and e.payload.get("state_snapshot_id")
    )

    return {
        "total_cycles": total,
        "approved": approved,
        "rejected": rejected,
        "approval_rate": approved / total if total else 0.0,
        "rejection_breakdown": {
            "by_reason": dict(rejection_reasons),
            "by_stage": dict(rejection_stages),
        },
        "provider_contribution": dict(provider_hits),
        "decisions_with_snapshot_id": with_snapshot,
        "snapshot_coverage": with_snapshot / len(decision_events) if decision_events else 1.0,
    }


def compute_outcome_metrics(events: list[EventEnvelope]) -> dict:
    closed = [e for e in events if e.event_type == ExecutionEventType.POSITION_CLOSED]
    pnls = [float(e.payload.get("pnl", 0)) for e in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit else 0.0
    )

    equity_curve = [0.0]
    for pnl in pnls:
        equity_curve.append(equity_curve[-1] + pnl)

    peak = 0.0
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        dd = peak - value
        max_dd = max(max_dd, dd)

    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev != 0:
            returns.append((equity_curve[i] - prev) / abs(prev))
        elif equity_curve[i] != 0:
            returns.append(1.0)

    sharpe = 0.0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = var**0.5
        if std > 0:
            sharpe = mean_r / std * (252**0.5)

    return {
        "total_trades": len(closed),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_pnl": sum(pnls),
    }
