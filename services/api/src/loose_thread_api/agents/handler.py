from collections.abc import Awaitable, Callable

from loose_thread_api.agents.interpreter import InterpreterOutput
from loose_thread_api.agents.repository import AgentRunRepository
from loose_thread_api.captures import CaptureRepository
from loose_thread_api.models.jobs import Job
from loose_thread_api.orchestration.worker import JobHandlerError

Interpret = Callable[..., Awaitable[InterpreterOutput]]


class InterpretationJobHandler:
    def __init__(
        self,
        *,
        captures: CaptureRepository,
        agent_runs: AgentRunRepository,
        interpret: Interpret,
        model: str,
        max_attempts: int,
    ) -> None:
        self._captures = captures
        self._agent_runs = agent_runs
        self._interpret = interpret
        self._model = model
        self._max_attempts = max_attempts

    async def __call__(self, job: Job) -> None:
        capture = await self._captures.get_for_interpretation(
            user_id=job.user_id,
            capture_id=job.entity_id,
        )
        if capture is None:
            raise JobHandlerError(
                "capture_not_interpretable",
                "Capture is missing or has no text",
                retryable=False,
            )

        run_id, started = await self._agent_runs.start_interpreter_run(
            job=job,
            model=self._model,
        )
        try:
            output = await self._interpret(
                raw_text=capture.raw_text,
                timezone=capture.timezone,
                client_created_at=capture.client_created_at.isoformat(),
                correlation_id=str(job.correlation_id),
            )
            await self._agent_runs.succeed_interpreter_run(
                run_id=run_id,
                job=job,
                output=output,
                started_monotonic=started,
                max_attempts=self._max_attempts,
                client_created_at=capture.client_created_at,
            )
        except Exception as exc:
            error_code = type(exc).__name__
            await self._agent_runs.fail_interpreter_run(
                run_id=run_id,
                job=job,
                started_monotonic=started,
                error_code=error_code,
            )
            raise JobHandlerError(
                "interpreter_failed",
                "Thought interpretation failed",
                retryable=True,
            ) from exc
