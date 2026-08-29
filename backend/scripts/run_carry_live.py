#!/usr/bin/env python3
"""Live / testnet runner for the delta-neutral basis carry.

Same CarryRunner loop as the paper backtest — only the snapshot source and the
executor are real. One cycle = poll snapshot -> decide -> plan -> place orders
-> apply fills -> accrue. State (position + cash) is persisted between cycles so
the process can restart.

Modes:
  --once       run a single cycle and exit
  --loop       APScheduler, every 8h (aligned before funding settlement)
  --dry-run    real prices, PaperCarryExecutor (no orders placed)
  --reconcile  compare persisted state to the exchange's actual positions

Credentials (env / .env): CARRY_SPOT_API_KEY, CARRY_SPOT_API_SECRET,
CARRY_FUTURES_API_KEY, CARRY_FUTURES_API_SECRET, CARRY_SANDBOX (default true).
Get testnet keys at testnet.binance.vision (spot) and
testnet.binancefuture.com (futures).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.carry import CarryManagerConfig, CarryRunner, PaperCarryExecutor
from src.carry.live_executor import CarryCredentials, CarryExchange, LiveCarryExecutor
from src.carry.live_state import load_position as _load_state
from src.carry.live_state import save_live_state as _save_state
from src.core.settings import get_settings


def _build_exchange(symbol: str) -> CarryExchange:
    s = get_settings()
    missing = [
        k
        for k, v in {
            "CARRY_SPOT_API_KEY": s.carry_spot_api_key,
            "CARRY_SPOT_API_SECRET": s.carry_spot_api_secret,
            "CARRY_FUTURES_API_KEY": s.carry_futures_api_key,
            "CARRY_FUTURES_API_SECRET": s.carry_futures_api_secret,
        }.items()
        if not v
    ]
    if missing:
        raise SystemExit(f"missing credentials: {', '.join(missing)} (see script docstring)")
    creds = CarryCredentials(
        spot_api_key=s.carry_spot_api_key,
        spot_secret=s.carry_spot_api_secret,
        futures_api_key=s.carry_futures_api_key,
        futures_secret=s.carry_futures_api_secret,
        sandbox=s.carry_sandbox,
    )
    return CarryExchange.binance(creds, symbol)


def _cycle(symbol: str, capital: float, *, dry_run: bool) -> None:
    exchange = _build_exchange(symbol)
    state, cash, spot_baseline = _load_state()
    if not state.in_market and cash == 0.0:
        cash = capital
    if spot_baseline is None and not dry_run:
        # first real cycle: record what's already sitting in the spot account,
        # net of any position the runner already holds (crash-recovery case)
        spot_baseline = exchange.open_positions()["spot_qty"] - state.spot_qty

    runner = CarryRunner(
        PaperCarryExecutor() if dry_run else LiveCarryExecutor(exchange),
        initial_capital=cash,
        config=CarryManagerConfig(capital_multiplier=1.5, min_trailing_funding_8h=-1.0),
    )
    runner.state, runner.cash = state, cash

    snap = exchange.snapshot()
    action = runner.step(snap)
    eq = runner.equity(snap.spot_px, snap.perp_mark_px)
    _save_state(
        runner.state,
        runner.cash,
        spot_baseline,
        symbol=symbol,
        mark={
            "at": snap.ts.isoformat(),
            "spot_px": snap.spot_px,
            "perp_px": snap.perp_mark_px,
            "funding_8h": snap.trailing_funding_8h,
            "equity": eq,
            "action": action,
            "dry_run": dry_run,
        },
    )

    st = runner.state
    tag = "  [DRY-RUN]" if dry_run else ""
    print(
        f"[{snap.ts:%Y-%m-%d %H:%M}] {symbol}  "
        f"funding_8h={snap.trailing_funding_8h * 100:.4f}%  action={action}  "
        f"spot_qty={st.spot_qty:.5f}  perp_qty={st.perp_qty:.5f}  "
        f"accrued={st.accrued_funding:.2f}  equity={eq:.2f}{tag}",
        flush=True,
    )


def _reconcile(symbol: str) -> None:
    exchange = _build_exchange(symbol)
    state, _, spot_baseline = _load_state()
    actual = exchange.open_positions()
    base = spot_baseline or 0.0
    runner_spot = actual["spot_qty"] - base
    print(f"persisted: spot={state.spot_qty:.5f} perp={state.perp_qty:.5f}", flush=True)
    print(
        f"exchange : spot={runner_spot:.5f} perp={actual['perp_qty']:.5f} "
        f"(raw {actual['spot_qty']:.5f} - baseline {base:.5f})",
        flush=True,
    )
    sd = abs(state.spot_qty - runner_spot)
    pd_ = abs(state.perp_qty - actual["perp_qty"])
    tol = max(state.spot_qty, 1e-6) * 0.02
    print("OK" if sd < tol and pd_ < tol else "MISMATCH — halt and investigate", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live/testnet basis-carry runner")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()

    if args.reconcile:
        _reconcile(args.symbol)
        return 0
    if args.once or args.dry_run:
        _cycle(args.symbol, args.capital, dry_run=args.dry_run)
        return 0
    if args.loop:
        from apscheduler.schedulers.blocking import BlockingScheduler

        sched = BlockingScheduler(timezone="UTC")
        sched.add_job(
            lambda: _cycle(args.symbol, args.capital, dry_run=False),
            "cron",
            hour="0,8,16",
            minute=50,  # ~10 min before funding settlement
        )
        print("carry runner scheduled at 00:50 / 08:50 / 16:50 UTC; Ctrl-C to stop", flush=True)
        _cycle(args.symbol, args.capital, dry_run=False)
        sched.start()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
