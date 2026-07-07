from __future__ import annotations

from typing import Any


def compare_features(
    stored: dict[str, Any],
    rebuilt: dict[str, Any],
    *,
    tolerance: float = 1e-6,
) -> dict:
    """Compare indicator dicts; returns drift report."""
    drifted: list[dict] = []
    all_keys = set(stored) | set(rebuilt)
    for key in sorted(all_keys):
        a = stored.get(key)
        b = rebuilt.get(key)
        if a is None or b is None:
            drifted.append({"key": key, "stored": a, "rebuilt": b, "reason": "missing"})
            continue
        if isinstance(a, int | float) and isinstance(b, int | float):
            if abs(float(a) - float(b)) > tolerance:
                drifted.append(
                    {
                        "key": key,
                        "stored": a,
                        "rebuilt": b,
                        "delta": float(b) - float(a),
                    }
                )
        elif a != b:
            drifted.append({"key": key, "stored": a, "rebuilt": b})
    return {
        "detected": len(drifted) > 0,
        "drift_count": len(drifted),
        "drifts": drifted,
    }
