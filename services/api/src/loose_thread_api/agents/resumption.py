import json
from dataclasses import dataclass
from importlib.resources import files
from uuid import UUID

from agents import Agent, RunConfig, Runner, set_default_openai_key
from agents.tracing.util import gen_trace_id

from loose_thread_api.config import Settings
from loose_thread_api.models.resumption import ResumptionAgentResult


@dataclass(frozen=True)
class ResumptionEvidence:
    id: UUID
    refined_text: str
    relation_type: str


@dataclass(frozen=True)
class ResumptionTelemetry:
    trace_id: str
    response_id: str | None
    usage: dict[str, int]


@dataclass(frozen=True)
class ResumptionOutput:
    result: ResumptionAgentResult
    telemetry: ResumptionTelemetry


class ResumptionAgent:
    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for resumption")
        set_default_openai_key(settings.openai_api_key.get_secret_value(), use_for_tracing=True)
        prompt = (
            files("loose_thread_api.agents")
            .joinpath("prompts/resumption_v1.md")
            .read_text(encoding="utf-8")
        )
        self._agent = Agent(
            name="Resumption Agent",
            instructions=prompt,
            model=settings.openai_model_resumption,
            output_type=ResumptionAgentResult,
        )

    async def resume(
        self,
        *,
        thought_id: UUID,
        refined_text: str,
        evidence: list[ResumptionEvidence],
        correlation_id: str,
    ) -> ResumptionOutput:
        trace_id = gen_trace_id()
        run = await Runner.run(
            self._agent,
            json.dumps(
                {
                    "selected_thought": {"id": str(thought_id), "refined_text": refined_text},
                    "linked_evidence": [
                        {
                            "id": str(item.id),
                            "refined_text": item.refined_text,
                            "relation_type": item.relation_type,
                        }
                        for item in evidence
                    ],
                },
                ensure_ascii=True,
            ),
            max_turns=1,
            run_config=RunConfig(
                workflow_name="Loose Thread resumption",
                trace_id=trace_id,
                group_id=correlation_id,
                trace_include_sensitive_data=False,
            ),
        )
        result = run.final_output_as(ResumptionAgentResult, raise_if_incorrect_type=True)
        self._validate_ids(evidence, result)
        usage = run.context_wrapper.usage
        return ResumptionOutput(
            result=result,
            telemetry=ResumptionTelemetry(
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
        evidence: list[ResumptionEvidence], result: ResumptionAgentResult
    ) -> None:
        allowed_ids = {item.id for item in evidence}
        if not set(result.supporting_thought_ids).issubset(allowed_ids):
            raise ValueError("resumption output cited unsupplied evidence")
