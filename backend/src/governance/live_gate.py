from __future__ import annotations

from src.core.settings import get_settings


class LiveGovernanceGate:
    """Lightweight gate for starting live mode. Full governance in Phase 8."""

    def allow_start(self, revision_id: str | None = None) -> bool:
        settings = get_settings()
        if settings.environment != "production":
            return True
        return revision_id is not None and len(revision_id) > 0
