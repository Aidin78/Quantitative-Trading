from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DecisionRecordRow, EventLogRow, SimulatedTradeRow
from src.db.repositories.decision import _extract_rejection_reason


def _parse_period(period: str) -> int:
    mapping = {"7d": 7, "30d": 30, "90d": 90, "365d": 365, "1y": 365}
    return mapping.get(period, 30)


async def compute_overview(session: AsyncSession, *, period: str = "30d") -> dict:
    days = _parse_period(period)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(DecisionRecordRow).where(DecisionRecordRow.created_at >= since)
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return {
            "period": period,
            "total_decisions": 0,
            "approval_rate": 0.0,
            "rejection_trends": [],
            "provider_contribution": [],
            "by_symbol": [],
            "outcome_summary": {},
        }

    approved = sum(1 for r in rows if r.result == "approved")
    daily: dict[str, dict[str, int]] = defaultdict(lambda: {"approved": 0, "rejected": 0})
    rejection_reasons: dict[str, int] = defaultdict(int)
    provider_hits: dict[str, int] = defaultdict(int)
    by_symbol: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "approved": 0})

    for row in rows:
        day = row.created_at.date().isoformat()
        sym = await _symbol_for_row(session, row)
        by_symbol[sym]["total"] += 1
        if row.result == "approved":
            daily[day]["approved"] += 1
            by_symbol[sym]["approved"] += 1
            for sig in row.decision_log.get("provider_signals", []):
                pid = sig.get("provider_id")
                if pid:
                    provider_hits[pid] += 1
        else:
            daily[day]["rejected"] += 1
            reason = _extract_rejection_reason(row.decision_log)
            rejection_reasons[reason] += 1

    trades = (await session.execute(select(SimulatedTradeRow))).scalars().all()
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]

    return {
        "period": period,
        "total_decisions": len(rows),
        "approval_rate": approved / len(rows) if rows else 0.0,
        "rejection_trends": [
            {
                "date": d,
                "approved": v["approved"],
                "rejected": v["rejected"],
            }
            for d, v in sorted(daily.items())
        ],
        "rejection_breakdown": dict(rejection_reasons),
        "provider_contribution": [
            {"provider_id": k, "count": v}
            for k, v in sorted(provider_hits.items(), key=lambda x: -x[1])
        ],
        "by_symbol": [
            {
                "symbol": sym,
                "total": data["total"],
                "approved": data["approved"],
                "approval_rate": data["approved"] / data["total"] if data["total"] else 0.0,
            }
            for sym, data in sorted(by_symbol.items())
        ],
        "outcome_summary": {
            "total_trades": len(pnls),
            "win_rate": len(wins) / len(pnls) if pnls else 0.0,
            "total_pnl": sum(pnls),
        },
    }


async def compute_heatmap(session: AsyncSession, *, period: str = "30d") -> dict:
    days = _parse_period(period)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(DecisionRecordRow).where(DecisionRecordRow.created_at >= since)
            )
        )
        .scalars()
        .all()
    )

    buckets: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"approved": 0, "rejected": 0}
    )
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for row in rows:
        hour = row.created_at.hour
        day = weekday_names[row.created_at.weekday()]
        key = (hour, day)
        if row.result == "approved":
            buckets[key]["approved"] += 1
        else:
            buckets[key]["rejected"] += 1

    data = []
    for (hour, day), counts in sorted(buckets.items()):
        total = counts["approved"] + counts["rejected"]
        data.append(
            {
                "hour": hour,
                "day": day,
                "win_rate": counts["approved"] / total if total else 0.0,
                "trades": total,
            }
        )
    return {"period": period, "data": data}


async def _symbol_for_row(session: AsyncSession, row: DecisionRecordRow) -> str:
    stmt = (
        select(EventLogRow.symbol).where(EventLogRow.correlation_id == row.correlation_id).limit(1)
    )
    sym = (await session.execute(stmt)).scalar_one_or_none()
    return sym or "UNKNOWN"
