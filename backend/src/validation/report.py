from __future__ import annotations

import json
from pathlib import Path

from src.validation.harness import ValidationResult


def format_report(result: ValidationResult) -> str:
    em = result.engine_metrics
    om = result.outcome_metrics
    lines = [
        f"Validation Run: {result.run_id}",
        f"Symbol: {result.config.symbol}  Timeframe: {result.config.timeframe}",
        f"Range: {result.config.start.isoformat()} -> {result.config.end.isoformat()}",
        "",
        "=== Engine Metrics ===",
        f"Cycles: {em.get('total_cycles', 0)}",
        f"Approval rate: {em.get('approval_rate', 0):.1%}",
        f"Approved / Rejected: {em.get('approved', 0)} / {em.get('rejected', 0)}",
        f"Rejection by reason: {em.get('rejection_breakdown', {}).get('by_reason', {})}",
        f"Provider contribution: {em.get('provider_contribution', {})}",
        "",
        "=== Outcome Metrics ===",
        f"Total trades: {om.get('total_trades', 0)}",
        f"Win rate: {om.get('win_rate', 0):.1%}",
        f"Profit factor: {om.get('profit_factor', 0):.2f}",
        f"Max drawdown: {om.get('max_drawdown', 0):.2f}",
        f"Sharpe ratio: {om.get('sharpe_ratio', 0):.2f}",
        f"Total PnL: {om.get('total_pnl', 0):.2f}",
        "",
        "=== Failure Analysis ===",
        *_format_failure_summary(om.get("failure_summary", {})),
    ]
    return "\n".join(lines)


def _format_failure_summary(summary: dict) -> list[str]:
    total_losses = summary.get("total_losses", 0)
    if not total_losses:
        return ["No losing trades to analyze."]

    lines = [f"{total_losses} losing trades attributed across regimes:"]
    for regime, share in sorted(
        summary.get("loss_share_by_regime", {}).items(), key=lambda kv: -kv[1]
    ):
        lines.append(f"  {share:.0%} occurred during {regime} regime")

    low_conf_share = summary.get("low_confidence_loss_share", 0)
    if low_conf_share:
        lines.append(f"  {low_conf_share:.0%} of losses came from low-confidence signals (<0.70)")

    lines.append(f"Average loss: {summary.get('avg_loss', 0):.2f}")
    lines.append(f"Average win: {summary.get('avg_win', 0):.2f}")

    unattributed = summary.get("unattributed_trades", 0)
    if unattributed:
        lines.append(f"({unattributed} trades could not be attributed to an entry regime)")
    return lines


def write_report(result: ValidationResult, output: Path) -> None:
    payload = {
        "run_id": result.run_id,
        "config": {
            "symbol": result.config.symbol,
            "timeframe": result.config.timeframe,
            "start": result.config.start.isoformat(),
            "end": result.config.end.isoformat(),
        },
        "engine_metrics": result.engine_metrics,
        "outcome_metrics": result.outcome_metrics,
        "cycle_count": len(result.cycles),
        "event_count": len(result.events),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
