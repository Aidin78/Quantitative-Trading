from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.governance.hypothesis_generator import (
    HypothesisDraft,
    HypothesisGenerationError,
    draft_hypothesis_from_failure_summary,
    generate_and_store_hypothesis,
)

_SAMPLE_SUMMARY = {
    "total_losses": 12,
    "loss_share_by_regime": {"UP_HIGH": 0.6667, "SIDEWAYS_NORMAL": 0.3333},
    "low_confidence_loss_share": 0.5,
    "avg_win": 40.0,
    "avg_loss": -30.0,
    "unattributed_trades": 0,
}


def _mock_parsed_response(draft: HypothesisDraft, *, stop_reason: str = "end_turn"):
    response = MagicMock()
    response.stop_reason = stop_reason
    response.parsed_output = draft
    return response


def test_draft_hypothesis_returns_validated_draft() -> None:
    draft = HypothesisDraft(
        observation="67% of losses occurred during UP_HIGH regime.",
        statement="Momentum signals degrade in high volatility regimes.",
        expected_effect="Reduce max drawdown and improve win rate in UP_HIGH regime.",
        proposed_change="Disable momentum signals when volatility percentile exceeds 80.",
    )
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.return_value = _mock_parsed_response(draft)
        result = draft_hypothesis_from_failure_summary(_SAMPLE_SUMMARY)

    assert result == draft
    assert "67%" in result.observation or "UP_HIGH" in result.observation


def test_draft_hypothesis_raises_on_refusal() -> None:
    draft = HypothesisDraft(
        observation="x", statement="x", expected_effect="x", proposed_change="x"
    )
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.return_value = _mock_parsed_response(
            draft, stop_reason="refusal"
        )
        with pytest.raises(HypothesisGenerationError, match="declined"):
            draft_hypothesis_from_failure_summary(_SAMPLE_SUMMARY)


def test_draft_hypothesis_raises_when_no_parsed_output() -> None:
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.parsed_output = None
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.return_value = response
        with pytest.raises(HypothesisGenerationError, match="structured"):
            draft_hypothesis_from_failure_summary(_SAMPLE_SUMMARY)


def test_draft_hypothesis_raises_on_empty_failure_summary() -> None:
    with pytest.raises(HypothesisGenerationError, match="no losing trades"):
        draft_hypothesis_from_failure_summary({"total_losses": 0})


def test_draft_hypothesis_wraps_api_status_error() -> None:
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.side_effect = anthropic.APIStatusError(
            "boom", response=MagicMock(status_code=500), body=None
        )
        with pytest.raises(HypothesisGenerationError, match="Claude API error"):
            draft_hypothesis_from_failure_summary(_SAMPLE_SUMMARY)


def test_draft_hypothesis_wraps_connection_error() -> None:
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.side_effect = anthropic.APIConnectionError(
            request=MagicMock()
        )
        with pytest.raises(HypothesisGenerationError, match="Could not reach"):
            draft_hypothesis_from_failure_summary(_SAMPLE_SUMMARY)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_and_store_hypothesis_persists_with_llm_creator(
    db_session: AsyncSession,
) -> None:
    draft = HypothesisDraft(
        observation="67% of losses occurred during UP_HIGH regime.",
        statement="Momentum signals degrade in high volatility regimes.",
        expected_effect="Reduce max drawdown in UP_HIGH regime.",
        proposed_change="Disable momentum signals above the 80th volatility percentile.",
    )
    with patch("src.governance.hypothesis_generator._build_client") as mock_build:
        mock_build.return_value.messages.parse.return_value = _mock_parsed_response(draft)
        hypothesis = await generate_and_store_hypothesis(
            db_session, _SAMPLE_SUMMARY, source_experiment_run_id="erun_source"
        )
    await db_session.commit()

    assert hypothesis.created_by == "llm"
    assert hypothesis.status == "open"
    assert hypothesis.source_experiment_run_id == "erun_source"
    assert hypothesis.proposed_change == draft.proposed_change
