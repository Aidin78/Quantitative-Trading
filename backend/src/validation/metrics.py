from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from src.core.contracts.event import EventEnvelope, EventFamily
from src.events.envelopes import DecisionEventType, ExecutionEventType
from src.runtime.models import CycleResult


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _derive_session_utc(event_time: datetime) -> Literal["ASIA", "EUROPE", "US", "OVERLAP"]:
    dt = event_time.astimezone(ZoneInfo("UTC"))
    hour = dt.hour
    if 12 <= hour < 16:
        return "OVERLAP"
    if 7 <= hour < 12:
        return "EUROPE"
    if 16 <= hour < 21:
        return "US"
    return "ASIA"


def _bucket_stats(pnls: list[float]) -> dict:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return {
        "trades": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "pnl": sum(pnls),
        "gross_profit": sum(wins),
        "gross_loss": abs(sum(losses)),
    }


def compute_monthly_breakdown(
    events: list[EventEnvelope],
    *,
    initial_capital: float = 10000.0,
) -> list[dict]:
    closed = sorted(
        [e for e in events if e.event_type == ExecutionEventType.POSITION_CLOSED],
        key=lambda e: e.event_time,
    )
    if not closed:
        return []

    by_month: dict[str, list[float]] = defaultdict(list)
    for event in closed:
        month_key = event.event_time.strftime("%Y-%m")
        by_month[month_key].append(float(event.payload.get("pnl", 0)))

    equity = initial_capital
    rows: list[dict] = []
    for month in sorted(by_month.keys()):
        pnls = by_month[month]
        month_start_equity = equity
        month_equity_curve = [month_start_equity]
        for pnl in pnls:
            month_equity_curve.append(month_equity_curve[-1] + pnl)
        equity = month_equity_curve[-1]

        peak = month_start_equity
        max_dd_pct = 0.0
        for value in month_equity_curve:
            peak = max(peak, value)
            if peak > 0:
                dd_pct = (peak - value) / peak * 100
                max_dd_pct = max(max_dd_pct, dd_pct)

        month_pnl = sum(pnls)
        wins = [p for p in pnls if p > 0]
        return_pct = (
            (equity - month_start_equity) / month_start_equity * 100
            if month_start_equity > 0
            else 0.0
        )
        rows.append(
            {
                "month": month,
                "trades": len(pnls),
                "win_rate": len(wins) / len(pnls) if pnls else 0.0,
                "pnl": month_pnl,
                "return_pct": return_pct,
                "max_drawdown_pct": max_dd_pct,
                "start_equity": month_start_equity,
                "end_equity": equity,
            }
        )
    return rows


def compute_diagnostics(events: list[EventEnvelope]) -> dict:
    closed = [e for e in events if e.event_type == ExecutionEventType.POSITION_CLOSED]

    by_exit_reason: dict[str, dict] = {}
    by_session: dict[str, dict] = {}
    by_side: dict[str, dict] = {}

    exit_buckets: dict[str, list[float]] = defaultdict(list)
    session_buckets: dict[str, list[float]] = defaultdict(list)
    side_buckets: dict[str, list[float]] = defaultdict(list)

    for event in closed:
        pnl = float(event.payload.get("pnl", 0))
        reason = str(event.payload.get("exit_reason") or "unknown")
        side = str(event.payload.get("side") or "unknown")
        session = _derive_session_utc(event.event_time)
        exit_buckets[reason].append(pnl)
        session_buckets[session].append(pnl)
        side_buckets[side].append(pnl)

    for key, pnls in exit_buckets.items():
        by_exit_reason[key] = _bucket_stats(pnls)
    for key, pnls in session_buckets.items():
        by_session[key] = _bucket_stats(pnls)
    for key, pnls in side_buckets.items():
        by_side[key] = _bucket_stats(pnls)

    return {
        "by_exit_reason": by_exit_reason,
        "by_session": by_session,
        "by_side": by_side,
    }


def compute_strategy_score(outcome: dict) -> float:
    return_pct = float(outcome.get("return_pct", 0))
    sharpe = float(outcome.get("sharpe_ratio", 0))
    win_rate = float(outcome.get("win_rate", 0))
    profit_factor = float(outcome.get("profit_factor", 0))
    max_dd_pct = float(outcome.get("max_drawdown_pct", 0))

    pf_term = profit_factor - 1 if profit_factor != float("inf") else 1.0

    score = (
        100
        * (
            0.35 * _clamp(return_pct / 10, -1, 1)
            + 0.25 * _clamp(sharpe / 2, -1, 1)
            + 0.20 * _clamp((win_rate - 0.5) * 2, -1, 1)
            + 0.20 * _clamp(pf_term, 0, 1)
        )
        - 1.5 * max_dd_pct
    )
    return round(score, 2)


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


def compute_outcome_metrics(
    events: list[EventEnvelope],
    *,
    initial_capital: float = 10000.0,
    ending_equity: float | None = None,
) -> dict:
    closed = [e for e in events if e.event_type == ExecutionEventType.POSITION_CLOSED]
    opened = [e for e in events if e.event_type == ExecutionEventType.POSITION_OPENED]
    rejected = [e for e in events if e.event_type == ExecutionEventType.ORDER_REJECTED]

    pnls = [float(e.payload.get("pnl", 0)) for e in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit else 0.0
    )

    equity_curve = [initial_capital]
    for pnl in pnls:
        equity_curve.append(equity_curve[-1] + pnl)

    peak = initial_capital
    max_dd = 0.0
    max_dd_pct = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        dd = peak - value
        max_dd = max(max_dd, dd)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, dd / peak * 100)

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

    final_equity = ending_equity if ending_equity is not None else equity_curve[-1]
    return_pct = (
        (final_equity - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0.0
    )

    outcome = {
        "total_trades": len(closed),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_pnl": sum(pnls),
        "initial_capital": initial_capital,
        "ending_equity": final_equity,
        "return_pct": return_pct,
        "equity_curve": equity_curve,
        "orders_rejected": len(rejected),
        "positions_opened": len(opened),
        "positions_closed": len(closed),
    }
    outcome["monthly_breakdown"] = compute_monthly_breakdown(
        events, initial_capital=initial_capital
    )
    outcome["diagnostics"] = compute_diagnostics(events)
    outcome["score"] = compute_strategy_score(outcome)
    return outcome
