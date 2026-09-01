import json
from dataclasses import dataclass
from importlib.resources import files

from agents import Agent, RunConfig, Runner, set_default_openai_key
from agents.tracing.util import gen_trace_id

from loose_thread_api.config import Settings
from loose_thread_api.models.interpretation import InterpretationResult


@dataclass(frozen=True)
class InterpreterTelemetry:
    trace_id: str
    response_id: str | None
    usage: dict[str, int]


@dataclass(frozen=True)
class InterpreterOutput:
    result: InterpretationResult
    telemetry: InterpreterTelemetry


class ThoughtInterpreter:
    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for thought interpretation")
        set_default_openai_key(
            settings.openai_api_key.get_secret_value(),
            use_for_tracing=True,
        )
        prompt = (
            files("loose_thread_api.agents")
            .joinpath("prompts/interpreter_v1.md")
            .read_text(encoding="utf-8")
        )
        self._agent = Agent(
            name="Thought Interpreter",
            instructions=prompt,
            model=settings.openai_model_interpreter,
            output_type=InterpretationResult,
        )

    async def interpret(
        self,
        *,
        raw_text: str,
        timezone: str,
        client_created_at: str,
        correlation_id: str,
    ) -> InterpreterOutput:
        trace_id = gen_trace_id()
        input_payload = json.dumps(
            {
                "raw_capture": raw_text,
                "timezone": timezone,
                "client_created_at": client_created_at,
            },
            ensure_ascii=True,
        )
        result = await Runner.run(
            self._agent,
            input_payload,
            max_turns=1,
            run_config=RunConfig(
                workflow_name="Loose Thread capture interpretation",
                trace_id=trace_id,
                group_id=correlation_id,
                trace_include_sensitive_data=False,
            ),
        )
        interpreted = result.final_output_as(
            InterpretationResult,
            raise_if_incorrect_type=True,
        )
        self._validate_provenance(raw_text, interpreted)
        usage = result.context_wrapper.usage
        return InterpreterOutput(
            result=interpreted,
            telemetry=InterpreterTelemetry(
                trace_id=trace_id,
                response_id=result.last_response_id,
                usage={
                    "requests": usage.requests,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                },
            ),
        )

    @staticmethod
    def _validate_provenance(raw_text: str, result: InterpretationResult) -> None:
        for thought in result.thoughts:
            if thought.raw_fragment not in raw_text:
                raise ValueError("interpreter returned a raw fragment absent from the capture")
            literal = thought.temporal.literal
            if literal is not None and literal not in raw_text:
                raise ValueError("interpreter returned temporal text absent from the capture")
            if thought.temporal.resolved_at is not None and thought.temporal.source is None:
                raise ValueError("resolved temporal data must identify its explicit source")
