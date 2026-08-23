"""Statistical signal-research pipeline (Phase 1-3): direction, magnitude, classification.

Separate from ``src/validation`` on purpose: validation exercises the real
Decision Engine on a built provider; this package only measures backward
vs. forward statistical relationships over raw OHLCV, with no engine, no
provider instantiation, and no execution. It exists to reject or shortlist
candidate signals *before* paying for a full validation run.
"""
