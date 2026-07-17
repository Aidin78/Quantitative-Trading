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


def _annualized_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    var = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = var**0.5
    if std <= 0:
        return 0.0
    return mean_r / std * (252**0.5)


def _annualized_sortino(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    downside = [min(0.0, r) for r in daily_returns]
    downside_var = sum(d**2 for d in downside) / len(daily_returns)
    downside_std = downside_var**0.5
    if downside_std <= 0:
        return 0.0
    return mean_r / downside_std * (252**0.5)


def compute_daily_equity_returns(
    events: list[EventEnvelope],
    *,
    initial_capital: float = 10000.0,
) -> tuple[list[float], list[str]]:
    """Build daily equity series from closed trades and return daily % changes."""
    closed = sorted(
        [e for e in events if e.event_type == ExecutionEventType.POSITION_CLOSED],
        key=lambda e: e.event_time,
    )
    if not closed:
        return [], []

    by_day: dict[str, float] = defaultdict(float)
    for event in closed:
        day_key = event.event_time.date().isoformat()
        by_day[day_key] += float(event.payload.get("pnl", 0))

    equity = initial_capital
    daily_returns: list[float] = []
    for day in sorted(by_day.keys()):
        pnl = by_day[day]
        prev = equity
        equity += pnl
        if prev != 0:
            daily_returns.append((equity - prev) / abs(prev))
        elif equity != 0:
            daily_returns.append(1.0)
    return daily_returns, sorted(by_day.keys())


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
            0.45 * _clamp(return_pct / 10, -1, 1)
            + 0.20 * _clamp(sharpe / 2, -1, 1)
            + 0.15 * _clamp((win_rate - 0.5) * 2, -1, 1)
            + 0.20 * _clamp(pf_term, 0, 1)
        )
        - 1.5 * max_dd_pct
    )
    return round(score, 2)


def compute_optimization_score(outcome: dict) -> float:
    score = compute_strategy_score(outcome)
    trades = int(outcome.get("total_trades", 0))
    if trades < 10:
        return min(score, -50.0)
    return score


def compute_engine_metrics(
    cycles: list[CycleResult],
    events: list[EventEnvelope],
) -> dict:
    acc = EngineMetricsAccumulator()
    for cycle in cycles:
        acc.observe(cycle)
    return acc.finalize(events)


class EngineMetricsAccumulator:
    """Incremental engine metrics so optimization runs need not retain CycleResult trees."""

    def __init__(self) -> None:
        self.total = 0
        self.approved = 0
        self.rejection_reasons: Counter[str] = Counter()
        self.rejection_stages: Counter[str] = Counter()
        self.provider_hits: Counter[str] = Counter()

    def observe(self, cycle: CycleResult) -> None:
        self.total += 1
        if cycle.decision.is_approved:
            self.approved += 1
            if cycle.decision.final_signal:
                for pid in cycle.decision.final_signal.contributing_providers:
                    self.provider_hits[pid] += 1
            return
        reason = cycle.decision.result.rejection_reason or "unknown"
        stage = cycle.decision.result.rejection_stage or "unknown"
        self.rejection_reasons[reason] += 1
        self.rejection_stages[stage] += 1

    def finalize(self, events: list[EventEnvelope]) -> dict:
        return _finalize_engine_metrics(
            total=self.total,
            approved=self.approved,
            rejection_reasons=self.rejection_reasons,
            rejection_stages=self.rejection_stages,
            provider_hits=self.provider_hits,
            events=events,
        )


def _finalize_engine_metrics(
    *,
    total: int,
    approved: int,
    rejection_reasons: Counter[str],
    rejection_stages: Counter[str],
    provider_hits: Counter[str],
    events: list[EventEnvelope],
) -> dict:
    rejected = total - approved
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

    daily_returns, _daily_dates = compute_daily_equity_returns(
        events, initial_capital=initial_capital
    )
    sharpe = _annualized_sharpe(daily_returns) if daily_returns else 0.0
    sortino = _annualized_sortino(daily_returns) if daily_returns else 0.0
    trade_sharpe = 0.0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = var**0.5
        if std > 0:
            trade_sharpe = mean_r / std * (252**0.5)

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
        "sortino_ratio": sortino,
        "trade_sharpe_ratio": trade_sharpe,
        "daily_return_count": len(daily_returns),
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
    outcome["optimization_score"] = compute_optimization_score(outcome)
    return outcome
