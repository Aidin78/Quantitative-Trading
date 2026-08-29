"""Delta-neutral carry position management — pure logic, no I/O.

Tracks a long-spot / short-perp pair, decides when to be in the market, keeps
the hedge delta-flat within a band, and accrues funding. A runner (live or
paper) feeds it prices and fills and acts on the plans it returns.

Sign conventions:
  - ``spot_qty``  >= 0  (units of base held long)
  - ``perp_qty``  >= 0  (units of base held *short* on the perp)
  - net delta     = spot_qty * spot_px - perp_qty * perp_px   (target ~ 0)
  - funding: a positive funding rate is paid by perp longs to perp shorts, so
    the short leg *receives* ``funding_rate * perp_qty * perp_px`` each period.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class CarryManagerConfig:
    #: capital tied up per 1x pair notional (spot + perp margin + buffer)
    capital_multiplier: float = 1.5
    #: hold the pair only while trailing funding (per 8h) is at/above this
    min_trailing_funding_8h: float = -1.0
    #: rebalance the hedge (perp size vs spot size) when |net delta| exceeds
    #: this fraction of notional — the perp leg is liquid, so keep it tight
    rebalance_band: float = 0.02
    #: re-strike the total pair notional to target only when it has drifted
    #: this far — loose, because a rally growing the (delta-neutral) notional is
    #: only a leverage problem once it is large, and re-striking crosses the
    #: spread on both legs
    resize_band: float = 0.15


@dataclass
class CarryPositionState:
    spot_qty: float = 0.0
    perp_qty: float = 0.0  # short size (>= 0)
    spot_entry_px: float = 0.0
    perp_entry_px: float = 0.0
    accrued_funding: float = 0.0
    flips: int = 0

    @property
    def in_market(self) -> bool:
        return self.spot_qty > 0 or self.perp_qty > 0


@dataclass(frozen=True)
class CarryTarget:
    hold: bool
    target_notional: float


@dataclass(frozen=True)
class RebalancePlan:
    spot_delta_qty: float  # + buy spot / - sell spot
    perp_delta_qty: float  # + increase short / - reduce short
    reason: str  # "open" | "close" | "resize" | "rebalance" | "noop"
    details: dict = field(default_factory=dict)

    @property
    def is_noop(self) -> bool:
        return self.reason == "noop"


class CarryPositionManager:
    def __init__(self, config: CarryManagerConfig | None = None) -> None:
        self.config = config or CarryManagerConfig()

    # --- read models -----------------------------------------------------
    def net_delta(self, state: CarryPositionState, spot_px: float, perp_px: float) -> float:
        return state.spot_qty * spot_px - state.perp_qty * perp_px

    def pair_notional(self, state: CarryPositionState, spot_px: float) -> float:
        return state.spot_qty * spot_px

    def equity(
        self, state: CarryPositionState, cash: float, spot_px: float, perp_px: float
    ) -> float:
        spot_val = state.spot_qty * spot_px
        perp_pnl = state.perp_qty * (state.perp_entry_px - perp_px)  # short
        return cash + spot_val + perp_pnl + state.accrued_funding

    # --- decisions -----------------------------------------------------
    def decide_target(self, *, trailing_funding_8h: float, equity: float) -> CarryTarget:
        hold = trailing_funding_8h >= self.config.min_trailing_funding_8h
        notional = max(0.0, equity) / self.config.capital_multiplier if hold else 0.0
        return CarryTarget(hold=hold, target_notional=notional)

    def plan(
        self,
        state: CarryPositionState,
        target: CarryTarget,
        *,
        spot_px: float,
        perp_px: float,
    ) -> RebalancePlan:
        cfg = self.config
        cur_notional = self.pair_notional(state, spot_px)

        if not target.hold:
            if state.in_market:
                return RebalancePlan(
                    spot_delta_qty=-state.spot_qty,
                    perp_delta_qty=-state.perp_qty,
                    reason="close",
                )
            return RebalancePlan(0.0, 0.0, "noop")

        if not state.in_market:
            qty = target.target_notional / spot_px if spot_px > 0 else 0.0
            if qty <= 0:
                return RebalancePlan(0.0, 0.0, "noop")
            return RebalancePlan(spot_delta_qty=qty, perp_delta_qty=qty, reason="open")

        # In market and want to stay. Delta hedge first (risk), then resize
        # (optimisation).
        delta = self.net_delta(state, spot_px, perp_px)
        if cur_notional > 0 and abs(delta) / cur_notional > cfg.rebalance_band:
            # bring perp short in line with the spot leg's current value
            desired_perp_qty = state.spot_qty * spot_px / perp_px if perp_px > 0 else state.perp_qty
            return RebalancePlan(
                spot_delta_qty=0.0,
                perp_delta_qty=desired_perp_qty - state.perp_qty,
                reason="rebalance",
                details={"delta_frac": delta / cur_notional},
            )

        # Re-strike the pair to target only on a large drift. A rally grows the
        # (delta-neutral) market notional without changing risk, but left
        # unchecked it becomes uncontrolled leverage, so trim it back once the
        # gap is wide. Wide band => infrequent, so the spread cost stays small.
        if target.target_notional > 0 and cur_notional > 0:
            drift = abs(cur_notional - target.target_notional) / target.target_notional
            if drift > cfg.resize_band:
                target_qty = target.target_notional / spot_px
                d = target_qty - state.spot_qty
                return RebalancePlan(
                    spot_delta_qty=d,
                    perp_delta_qty=d,
                    reason="resize",
                    details={"drift": drift},
                )

        return RebalancePlan(0.0, 0.0, "noop")

    # --- state transitions -------------------------------------------
    def apply_fill(
        self,
        state: CarryPositionState,
        *,
        spot_fill_qty: float,
        spot_fill_px: float,
        perp_fill_qty: float,
        perp_fill_px: float,
        fee: float = 0.0,
    ) -> tuple[CarryPositionState, float]:
        """Apply a fill; return ``(new_state, cash_flow)``.

        ``cash_flow`` is everything that hits cash: the spot leg's buy/sell
        proceeds (buy = negative), the *realised* P&L when the perp short is
        reduced (short profits when covered below entry), minus ``fee``. The
        perp leg posts/frees margin rather than spending cash, so increasing
        the short is cash-neutral here; its running P&L is marked by
        ``equity()`` instead.
        """
        new_spot = state.spot_qty + spot_fill_qty
        new_perp = state.perp_qty + perp_fill_qty

        cash_flow = -spot_fill_qty * spot_fill_px - fee
        if perp_fill_qty < 0 and state.perp_qty > 0:
            closed = min(-perp_fill_qty, state.perp_qty)
            cash_flow += closed * (state.perp_entry_px - perp_fill_px)  # short realised P&L

        spot_entry = state.spot_entry_px
        if spot_fill_qty > 0:
            spot_entry = (
                (state.spot_qty * state.spot_entry_px + spot_fill_qty * spot_fill_px) / new_spot
                if new_spot > 0
                else spot_fill_px
            )
        perp_entry = state.perp_entry_px
        if perp_fill_qty > 0:
            perp_entry = (
                (state.perp_qty * state.perp_entry_px + perp_fill_qty * perp_fill_px) / new_perp
                if new_perp > 0
                else perp_fill_px
            )

        flips = state.flips + (1 if (not state.in_market and (new_spot > 0 or new_perp > 0)) else 0)
        flips += 1 if (state.in_market and new_spot <= 1e-12 and new_perp <= 1e-12) else 0

        new_state = replace(
            state,
            spot_qty=max(0.0, new_spot),
            perp_qty=max(0.0, new_perp),
            spot_entry_px=spot_entry if new_spot > 0 else 0.0,
            perp_entry_px=perp_entry if new_perp > 0 else 0.0,
            flips=flips,
        )
        return new_state, cash_flow

    def accrue_funding(
        self, state: CarryPositionState, *, funding_rate: float, perp_px: float
    ) -> CarryPositionState:
        received = funding_rate * state.perp_qty * perp_px
        return replace(state, accrued_funding=state.accrued_funding + received)
