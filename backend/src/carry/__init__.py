"""Delta-neutral basis-carry strategy: hold spot, short the perpetual of the
same notional, collect the funding rate. Distinct from the Engine-Centric
directional pipeline — it is a mechanical, market-neutral income strategy, so
it lives as its own module with its own backtester (same spirit as
``src/research/``: measure it honestly before paying for a full runtime
integration).

See ``docs/development/basis-carry-findings.md``.
"""

from src.carry.basis_carry import BasisCarryConfig, BasisCarryResult, simulate_basis_carry
from src.carry.blended_book import BlendConfig, BlendedBookResult, build_blended_book
from src.carry.funding_data import load_funding_history

__all__ = [
    "BasisCarryConfig",
    "BasisCarryResult",
    "BlendConfig",
    "BlendedBookResult",
    "build_blended_book",
    "load_funding_history",
    "simulate_basis_carry",
]
