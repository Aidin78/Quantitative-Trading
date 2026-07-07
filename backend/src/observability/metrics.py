from __future__ import annotations

from prometheus_client import Counter, generate_latest

DECISIONS_TOTAL = Counter(
    "qtp_decisions_total",
    "Total decisions processed",
    ["result"],
)
VALIDATION_RUNS_TOTAL = Counter(
    "qtp_validation_runs_total",
    "Total validation runs",
    ["status"],
)
LIVE_CYCLES_TOTAL = Counter(
    "qtp_live_cycles_total",
    "Total live scheduler cycles",
    ["mode"],
)


def metrics_payload() -> bytes:
    return generate_latest()
