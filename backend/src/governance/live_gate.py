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
        if not await has_successful_validation(session, revision_id):
            return False

        if settings.require_champion_candidate:
            from src.governance.candidate_store import (
                revision_has_candidate_lineage,
                revision_has_champion,
            )

            # Only enforced for revisions that actually went through the
            # candidate workflow -- a revision with no candidate lineage at
            # all (e.g. a manual/legacy experiment) is not retroactively
            # blocked by turning this flag on.
            if await revision_has_candidate_lineage(session, revision_id):
                return await revision_has_champion(session, revision_id)

        return True
