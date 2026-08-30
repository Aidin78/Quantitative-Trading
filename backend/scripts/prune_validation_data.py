#!/usr/bin/env python3
"""Drop the bulky forensic tables that validation runs leave behind.

A validation run (before the ``persist_stream`` default flipped to False) wrote
its whole event stream plus a feature_set and state_snapshot per bar — easily
multiple GB per run. None of it is needed once the run's summary metrics and
closed trades are stored; it only ever backed forensic replay of that one run.

This TRUNCATEs:  event_log, decision_records, feature_sets, state_snapshots,
                 simulated_trades, backtest_runs, experiment_runs, experiments,
                 fills, orders
and keeps:       config_revisions, hypotheses, candidates, candidate_evaluations
                 (governance history — tiny), plus live/paper decision_records
                 unless --all is given.

Usage:
  poetry run python scripts/prune_validation_data.py --dry-run
  poetry run python scripts/prune_validation_data.py --yes
  poetry run python scripts/prune_validation_data.py --yes --all   # also live/paper
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.db.session import get_async_engine  # noqa: E402

# order doesn't matter (no FKs between them), but keep it readable
_FULL_TRUNCATE = [
    "event_log",
    "feature_sets",
    "state_snapshots",
    "simulated_trades",
    "backtest_runs",
    "experiment_runs",
    "experiments",
    "fills",
    "orders",
]


async def _run(*, dry_run: bool, wipe_all_decisions: bool) -> None:
    engine = get_async_engine()
    async with engine.begin() as conn:
        sizes = (
            await conn.execute(
                text(
                    "SELECT relname, n_live_tup, "
                    "pg_size_pretty(pg_total_relation_size(relid)) "
                    "FROM pg_catalog.pg_stat_user_tables "
                    "WHERE schemaname = 'public' AND pg_total_relation_size(relid) > 16384 "
                    "ORDER BY pg_total_relation_size(relid) DESC"
                )
            )
        ).all()
        print("current tables:")
        for name, rows, size in sizes:
            print(f"  {name:<24} {rows:>12,} rows   {size}")

        if dry_run:
            print("\n[dry-run] nothing changed. Re-run with --yes to prune.")
            return

        for table in _FULL_TRUNCATE:
            await conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY"))
        if wipe_all_decisions:
            await conn.execute(text("TRUNCATE TABLE decision_records RESTART IDENTITY"))
        else:
            await conn.execute(
                text("DELETE FROM decision_records WHERE mode NOT IN ('live', 'paper')")
            )
        print(
            "\npruned. run VACUUM FULL to hand the disk back to the OS "
            "(needs an exclusive lock)."
        )
    await engine.dispose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show table sizes, change nothing")
    ap.add_argument("--yes", action="store_true", help="actually truncate")
    ap.add_argument(
        "--all",
        dest="wipe_all_decisions",
        action="store_true",
        help="also drop live/paper decision_records (default keeps them)",
    )
    args = ap.parse_args()
    if not args.dry_run and not args.yes:
        ap.error("pass --dry-run to preview or --yes to prune")
    asyncio.run(_run(dry_run=args.dry_run, wipe_all_decisions=args.wipe_all_decisions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
