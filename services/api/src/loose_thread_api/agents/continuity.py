import json
from dataclasses import dataclass
from importlib.resources import files
from uuid import UUID

from agents import Agent, RunConfig, Runner, set_default_openai_key
from agents.tracing.util import gen_trace_id

from loose_thread_api.config import Settings
from loose_thread_api.models.continuity import ContinuityResult


@dataclass(frozen=True)
class ContinuityCandidate:
    id: UUID
    refined_text: str
    kind: str
    commitment_strength: str
    created_at: str
    similarity: float


@dataclass(frozen=True)
class ContinuityTelemetry:
    trace_id: str
    response_id: str | None
    usage: dict[str, int]


@dataclass(frozen=True)
class ContinuityOutput:
    result: ContinuityResult
    telemetry: ContinuityTelemetry


class ContinuityAgent:
    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for continuity analysis")
        set_default_openai_key(settings.openai_api_key.get_secret_value(), use_for_tracing=True)
        prompt = (
            files("loose_thread_api.agents")
            .joinpath("prompts/continuity_v1.md")
            .read_text(encoding="utf-8")
        )
        self._agent = Agent(
            name="Continuity Agent",
            instructions=prompt,
            model=settings.openai_model_continuity,
            output_type=ContinuityResult,
        )

    async def relate(
        self,
        *,
        thought_id: UUID,
        refined_text: str,
        kind: str,
        commitment_strength: str,
        candidates: list[ContinuityCandidate],
        correlation_id: str,
    ) -> ContinuityOutput:
        trace_id = gen_trace_id()
        payload = json.dumps(
            {
                "new_thought": {
                    "id": str(thought_id),
                    "refined_text": refined_text,
                    "kind": kind,
                    "commitment_strength": commitment_strength,
                },
                "candidates": [
                    {
                        "id": str(candidate.id),
                        "refined_text": candidate.refined_text,
                        "kind": candidate.kind,
                        "commitment_strength": candidate.commitment_strength,
                        "created_at": candidate.created_at,
                        "similarity": candidate.similarity,
                    }
                    for candidate in candidates
                ],
            },
            ensure_ascii=True,
        )
        run = await Runner.run(
            self._agent,
            payload,
            max_turns=1,
            run_config=RunConfig(
                workflow_name="Loose Thread continuity analysis",
                trace_id=trace_id,
                group_id=correlation_id,
                trace_include_sensitive_data=False,
            ),
        )
        result = run.final_output_as(ContinuityResult, raise_if_incorrect_type=True)
        self._validate_ids(thought_id, candidates, result)
        usage = run.context_wrapper.usage
        return ContinuityOutput(
            result=result,
            telemetry=ContinuityTelemetry(
                trace_id=trace_id,
                response_id=run.last_response_id,
                usage={
                    "requests": usage.requests,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                },
            ),
        )

    @staticmethod
    def _validate_ids(
        thought_id: UUID,
        candidates: list[ContinuityCandidate],
        result: ContinuityResult,
    ) -> None:
        candidate_ids = {candidate.id for candidate in candidates}
        for relationship in result.relationships:
            if relationship.from_thought_id != thought_id:
                raise ValueError("continuity output changed the source thought")
            if relationship.to_thought_id not in candidate_ids:
                raise ValueError("continuity output referenced an unsupplied candidate")
