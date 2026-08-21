from __future__ import annotations

import json

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.governance import Hypothesis
from src.core.settings import get_settings
from src.governance.hypothesis_store import create_hypothesis

_MODEL = "claude-opus-5"

_SYSTEM_PROMPT = """You are a research assistant for a quantitative trading platform. \
You read a failure-analysis summary from a completed backtest and draft ONE hypothesis \
for what to try next.

Rules:
- Every claim in `observation` must be a number or fact taken directly from the summary \
you were given. Never invent a percentage, regime name, or trade count that isn't in the \
input.
- `statement` is your causal explanation for the observation -- a plausible mechanism, \
not a repetition of the observation.
- `expected_effect` names the specific metric(s) you expect to improve and roughly how \
(e.g. "reduce max drawdown", "raise win rate in HIGH volatility regimes") -- not a vague \
"performance should improve".
- `proposed_change` must be a concrete, implementable configuration or provider change \
(a parameter to adjust, a signal to gate, a filter to add) -- not "investigate further" \
or "consider reviewing".
- You are drafting a hypothesis for a human to review and a deterministic pipeline to \
test. You are not deciding whether the hypothesis is correct, and you never claim the \
proposed change will definitely work."""


class HypothesisDraft(BaseModel):
    observation: str = Field(description="What the failure summary shows, grounded in its numbers")
    statement: str = Field(description="The causal hypothesis explaining the observation")
    expected_effect: str = Field(description="Specific metric(s) expected to improve, and how")
    proposed_change: str = Field(description="A concrete, implementable configuration change")


class HypothesisGenerationError(Exception):
    """Raised when Claude declines, times out, or returns something that fails validation."""


def _build_client() -> anthropic.Anthropic:
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()


def draft_hypothesis_from_failure_summary(failure_summary: dict) -> HypothesisDraft:
    """One Claude call, structured output, grounded in the exact dict
    validation.metrics.summarize_failures() produces. Returns a draft only --
    this function never writes to the database and never decides whether the
    hypothesis is accepted; see generate_and_store_hypothesis for persistence,
    and CandidateEvaluator (a separate, deterministic module) for acceptance.
    """
    if not failure_summary or not failure_summary.get("total_losses"):
        raise HypothesisGenerationError(
            "failure_summary has no losing trades to analyze -- nothing to hypothesize about"
        )

    client = _build_client()
    user_content = (
        "Failure analysis summary from a completed backtest run "
        "(JSON, produced by validation.metrics.summarize_failures):\n\n"
        f"{json.dumps(failure_summary, indent=2)}\n\n"
        "Draft one hypothesis for what to try next."
    )

    try:
        response = client.messages.parse(
            model=_MODEL,
            max_tokens=2000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=HypothesisDraft,
        )
    except anthropic.APIStatusError as exc:
        raise HypothesisGenerationError(f"Claude API error: {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise HypothesisGenerationError(f"Could not reach Claude API: {exc}") from exc

    if response.stop_reason == "refusal":
        raise HypothesisGenerationError("Claude declined to draft a hypothesis for this input")
    if response.parsed_output is None:
        raise HypothesisGenerationError("Claude did not return a structured hypothesis draft")

    return response.parsed_output


async def generate_and_store_hypothesis(
    session: AsyncSession,
    failure_summary: dict,
    *,
    source_experiment_run_id: str | None = None,
) -> Hypothesis:
    """Draft with Claude, then persist through the same create_hypothesis path
    a human-authored hypothesis uses -- created_by="llm" is the only
    difference, kept visible everywhere the schema surfaces it so a
    reviewer always knows which hypotheses were machine-drafted.
    """
    draft = draft_hypothesis_from_failure_summary(failure_summary)
    return await create_hypothesis(
        session,
        observation=draft.observation,
        statement=draft.statement,
        expected_effect=draft.expected_effect,
        proposed_change=draft.proposed_change,
        source_experiment_run_id=source_experiment_run_id,
        created_by="llm",
    )
