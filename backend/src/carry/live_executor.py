"""Live (or testnet) execution for the delta-neutral carry.

The carry needs two venues at once: a spot account (long leg) and a perpetual
futures account (short leg). On Binance these are separate endpoints with
separate API keys, and both have their own testnet — ``sandbox=True`` points
ccxt at ``testnet.binance.vision`` / ``testnet.binancefuture.com``.

``CarryExchange`` wraps the two ccxt clients; ``LiveCarryExecutor`` turns a
``RebalancePlan`` into real market orders and reports the actual fills. The
same ``CarryRunner`` loop drives it — only the executor and the snapshot
source change vs the paper run.

Safety: the two legs are placed in sequence. If the second leg fails after the
first filled, the executor unwinds the first leg immediately (so the book is
never left directionally exposed) and raises ``PartialCarryFill``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.carry.carry_runner import ExecReport
from src.carry.perp_provider import PerpSnapshot
from src.carry.position_manager import RebalancePlan


class PartialCarryFill(RuntimeError):
    """One leg filled, the other failed; the filled leg was unwound."""


@dataclass(frozen=True)
class Fill:
    qty: float
    avg_price: float
    fee: float


@dataclass(frozen=True)
class CarryCredentials:
    spot_api_key: str
    spot_secret: str
    futures_api_key: str
    futures_secret: str
    sandbox: bool = True


class CarryExchange:
    """A spot ccxt client + a futures ccxt client for one symbol."""

    def __init__(self, spot_client, futures_client, symbol: str, *, trail_prints: int = 3) -> None:
        self._spot = spot_client
        self._fut = futures_client
        self.symbol = symbol
        self._trail_prints = trail_prints
        base, quote = symbol.split("/")
        self._perp = f"{base}/{quote}:{quote}"

    @classmethod
    def binance(cls, creds: CarryCredentials, symbol: str) -> CarryExchange:
        import ccxt

        spot = ccxt.binance(
            {"apiKey": creds.spot_api_key, "secret": creds.spot_secret, "enableRateLimit": True}
        )
        fut = ccxt.binance(
            {
                "apiKey": creds.futures_api_key,
                "secret": creds.futures_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if creds.sandbox:
            spot.set_sandbox_mode(True)
            fut.set_sandbox_mode(True)
        return cls(spot, fut, symbol)

    # --- market data -------------------------------------------------
    def snapshot(self) -> PerpSnapshot:
        spot_px = float(self._spot.fetch_ticker(self.symbol)["last"])
        fr = self._fut.fetch_funding_rate(self._perp)
        perp_px = float(fr.get("markPrice") or self._fut.fetch_ticker(self._perp)["last"])
        hist = self._fut.fetch_funding_rate_history(self._perp, limit=self._trail_prints)
        trail = (
            sum(h["fundingRate"] for h in hist) / len(hist) if hist else float(fr["fundingRate"])
        )
        return PerpSnapshot(
            ts=datetime.now().astimezone(),
            symbol=self.symbol,
            spot_px=spot_px,
            perp_mark_px=perp_px,
            funding_rate=float(fr["fundingRate"]),
            trailing_funding_8h=float(trail),
            is_funding_time=True,
        )

    # --- orders ----------------------------------------------------
    def _fill_from_order(self, order: dict) -> Fill:
        qty = float(order.get("filled") or order.get("amount") or 0.0)
        price = float(order.get("average") or order.get("price") or 0.0)
        fee = 0.0
        for f in order.get("fees") or ([order["fee"]] if order.get("fee") else []):
            if f and f.get("cost") is not None:
                fee += float(f["cost"])
        return Fill(qty=qty, avg_price=price, fee=fee)

    def market_spot(self, side: str, qty: float) -> Fill:
        order = self._spot.create_order(self.symbol, "market", side, abs(qty))
        return self._fill_from_order(order)

    def market_perp(self, side: str, qty: float, *, reduce_only: bool = False) -> Fill:
        params = {"reduceOnly": True} if reduce_only else {}
        order = self._fut.create_order(self._perp, "market", side, abs(qty), None, params)
        return self._fill_from_order(order)

    def open_positions(self) -> dict:
        """{'spot_qty', 'perp_qty'} for reconciliation."""
        spot_bal = self._spot.fetch_balance()
        base = self.symbol.split("/")[0]
        spot_qty = float(spot_bal.get(base, {}).get("free", 0.0) or 0.0)
        perp = 0.0
        for p in self._fut.fetch_positions([self._perp]):
            if p.get("symbol") == self._perp:
                perp = abs(float(p.get("contracts") or p.get("contractSize") or 0.0))
        return {"spot_qty": spot_qty, "perp_qty": perp}


class LiveCarryExecutor:
    def __init__(self, exchange: CarryExchange) -> None:
        self.exchange = exchange

    def execute(self, plan: RebalancePlan, *, spot_px: float, perp_px: float) -> ExecReport | None:
        if plan.is_noop:
            return None

        spot_fill: Fill | None = None
        if abs(plan.spot_delta_qty) > 1e-9:
            side = "buy" if plan.spot_delta_qty > 0 else "sell"
            spot_fill = self.exchange.market_spot(side, plan.spot_delta_qty)

        try:
            perp_fill: Fill | None = None
            if abs(plan.perp_delta_qty) > 1e-9:
                # + => increase short (sell), - => reduce short (buy, reduceOnly)
                if plan.perp_delta_qty > 0:
                    perp_fill = self.exchange.market_perp("sell", plan.perp_delta_qty)
                else:
                    perp_fill = self.exchange.market_perp(
                        "buy", plan.perp_delta_qty, reduce_only=True
                    )
        except Exception as exc:  # noqa: BLE001 - unwind then re-raise
            if spot_fill is not None and spot_fill.qty > 0:
                unwind = "sell" if plan.spot_delta_qty > 0 else "buy"
                self.exchange.market_spot(unwind, spot_fill.qty)
            raise PartialCarryFill(
                f"perp leg failed after spot filled ({spot_fill}); spot unwound"
            ) from exc

        s_qty = (spot_fill.qty if spot_fill else 0.0) * (1 if plan.spot_delta_qty >= 0 else -1)
        p_qty = (perp_fill.qty if perp_fill else 0.0) * (1 if plan.perp_delta_qty >= 0 else -1)
        return ExecReport(
            spot_fill_qty=s_qty,
            spot_fill_px=spot_fill.avg_price if spot_fill else spot_px,
            perp_fill_qty=p_qty,
            perp_fill_px=perp_fill.avg_price if perp_fill else perp_px,
            fee=(spot_fill.fee if spot_fill else 0.0) + (perp_fill.fee if perp_fill else 0.0),
            reason=plan.reason,
        )
