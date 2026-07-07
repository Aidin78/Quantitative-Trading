from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.contracts.decision import Decision


@dataclass(frozen=True)
class DecisionDiff:
    correlation_id: str
    original_result: str
    reexecuted_result: str
    original_side: str | None
    reexecuted_side: str | None
    original_rejection_reason: str | None
    reexecuted_rejection_reason: str | None
    original_confidence: float | None
    reexecuted_confidence: float | None
    changed: bool
    revision_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "original": {
                "result": self.original_result,
                "side": self.original_side,
                "rejection_reason": self.original_rejection_reason,
                "confidence": self.original_confidence,
            },
            "reexecuted": {
                "result": self.reexecuted_result,
                "side": self.reexecuted_side,
                "rejection_reason": self.reexecuted_rejection_reason,
                "confidence": self.reexecuted_confidence,
            },
            "changed": self.changed,
            "revision_id": self.revision_id,
        }


def build_decision_diff(
    correlation_id: str,
    original: Decision,
    reexecuted: Decision,
    *,
    revision_id: str | None = None,
) -> DecisionDiff:
    orig_side = None
    re_side = None
    orig_conf = None
    re_conf = None
    if original.is_approved and original.final_signal:
        orig_side = original.final_signal.side
        orig_conf = original.final_signal.confidence
    if reexecuted.is_approved and reexecuted.final_signal:
        re_side = reexecuted.final_signal.side
        re_conf = reexecuted.final_signal.confidence
    changed = (
        original.result.value != reexecuted.result.value
        or orig_side != re_side
        or original.result.rejection_reason != reexecuted.result.rejection_reason
    )
    return DecisionDiff(
        correlation_id=correlation_id,
        original_result=original.result.value,
        reexecuted_result=reexecuted.result.value,
        original_side=orig_side,
        reexecuted_side=re_side,
        original_rejection_reason=original.result.rejection_reason,
        reexecuted_rejection_reason=reexecuted.result.rejection_reason,
        original_confidence=orig_conf,
        reexecuted_confidence=re_conf,
        changed=changed,
        revision_id=revision_id,
    )
