"""Read-only view of the deployable book: the delta-neutral carry sleeve and
the trend-core sleeve, plus the target blend.

Neither sleeve runs inside the Decision Engine pipeline — carry is
``scripts/run_carry_live.py`` (state in ``data/carry_live_state.json``), core is
the live/paper engine on the ``core_long`` revision. This endpoint just reports
what each one persisted; it never places an order or hits an exchange.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.api.services.live_service import get_live_manager
from src.carry.live_state import load_live_state

router = APIRouter(
    prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)]
)

# Blended book target (docs/development/basis-carry-findings.md).
_CARRY_TARGET_WEIGHT = 0.70
_CORE_TARGET_WEIGHT = 0.30


def _carry_sleeve() -> dict:
    raw = load_live_state()
    if raw is None:
        return {"status": "not_started"}

    st = raw.get("state", {})
    mark = raw.get("mark") or {}
    spot_qty = float(st.get("spot_qty", 0.0))
    perp_qty = float(st.get("perp_qty", 0.0))
    in_market = abs(spot_qty) > 1e-9 or abs(perp_qty) > 1e-9

    spot_px = float(mark.get("spot_px") or 0.0)
    net_delta_qty = spot_qty - perp_qty
    notional = spot_qty * spot_px if spot_px else 0.0
    net_delta_pct = (net_delta_qty * spot_px / notional * 100.0) if notional else 0.0

    funding_8h = mark.get("funding_8h")
    funding_8h_pct = float(funding_8h) * 100.0 if funding_8h is not None else None
    funding_apr_pct = float(funding_8h) * 3 * 365 * 100.0 if funding_8h is not None else None

    return {
        "status": "in_market" if in_market else "flat",
        "symbol": raw.get("symbol"),
        "updated_at": raw.get("ts"),
        "marked_at": mark.get("at"),
        "is_dry_run": bool(mark.get("dry_run", False)),
        "equity": mark.get("equity"),
        "cash": float(raw.get("cash", 0.0)),
        "accrued_funding": float(st.get("accrued_funding", 0.0)),
        "funding_8h_pct": funding_8h_pct,
        "funding_apr_pct": funding_apr_pct,
        "spot_qty": spot_qty,
        "perp_qty": perp_qty,
        "notional": notional,
        "net_delta_qty": net_delta_qty,
        "net_delta_pct": net_delta_pct,
        "flips": int(st.get("flips", 0)),
        "last_action": mark.get("action"),
    }


def _core_sleeve() -> dict:
    live = get_live_manager().status_dict()
    return {
        "status": live.get("status", "stopped"),
        "mode": live.get("mode"),
        "revision_id": live.get("revision_id"),
        "experiment_id": live.get("experiment_id"),
        "last_run_at": live.get("last_run_at"),
        "last_error": live.get("last_error"),
        "jobs": live.get("jobs", []),
    }


@router.get("")
async def portfolio() -> dict:
    carry = _carry_sleeve()
    core = _core_sleeve()

    carry_equity = carry.get("equity") if isinstance(carry.get("equity"), int | float) else None
    blend: dict = {
        "target_carry_pct": _CARRY_TARGET_WEIGHT * 100.0,
        "target_core_pct": _CORE_TARGET_WEIGHT * 100.0,
        "combined_equity": carry_equity,
        "note": (
            "Core-sleeve equity is not tracked here yet; "
            "the combined figure is the carry sleeve only."
        ),
    }
    return {"carry": carry, "core": core, "blend": blend}
