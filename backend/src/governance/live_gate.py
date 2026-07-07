from __future__ import annotations

from src.core.settings import get_settings


class LiveGovernanceGate:
    """Gate for starting live mode — full checks in production."""

    def allow_start_dev(self, revision_id: str | None = None) -> bool:
        settings = get_settings()
        if settings.environment != "production":
            return True
        return revision_id is not None and len(revision_id) > 0

    async def allow_start(self, session, revision_id: str | None = None) -> bool:  # noqa: ANN001
        settings = get_settings()
        if settings.environment != "production":
            return True
        if not revision_id:
            return False
        from src.governance.experiment_store import has_successful_validation
        from src.governance.revision_store import get_revision

        revision = await get_revision(session, revision_id)
        if revision is None:
            return False
        return await has_successful_validation(session, revision_id)
