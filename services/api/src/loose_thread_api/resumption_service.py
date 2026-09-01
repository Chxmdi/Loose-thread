from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid4

import asyncpg

from loose_thread_api.agents.resumption import (
    ResumptionEvidence,
    ResumptionOutput,
)
from loose_thread_api.models.resumption import (
    LinkedThoughtView,
    ResumptionResponse,
)


@dataclass(frozen=True)
class ResumableThought:
    id: UUID
    refined_text: str
    raw_fragment: str
    is_open: bool
    kind: str


Resume = Callable[..., Awaitable[ResumptionOutput]]


class ResumptionService:
    def __init__(self, pool: asyncpg.Pool, *, resume: Resume, model: str) -> None:
        self._pool = pool
        self._resume = resume
        self._model = model

    async def get(self, *, user_id: UUID, thought_id: UUID) -> ResumptionResponse | None:
        row = await self._pool.fetchrow(
            """
            select id, refined_text, raw_fragment,
                   coalesce((open_loop ->> 'is_open')::boolean, false) as is_open, kind
            from public.thoughts
            where id = $1 and user_id = $2 and not is_deleted
            """,
            thought_id,
            user_id,
        )
        if row is None:
            return None
        thought = ResumableThought(**dict(row))
        evidence_rows = await self._pool.fetch(
            """
            select other.id, other.refined_text, relationship.relation_type
            from public.thought_relationships relationship
            join public.thoughts other
              on other.user_id = relationship.user_id
             and other.id = case
                 when relationship.from_thought_id = $1 then relationship.to_thought_id
                 else relationship.from_thought_id
             end
            where relationship.user_id = $2
              and (relationship.from_thought_id = $1 or relationship.to_thought_id = $1)
              and not other.is_deleted
            order by relationship.confidence desc nulls last, relationship.created_at desc
            limit 3
            """,
            thought_id,
            user_id,
        )
        evidence = [ResumptionEvidence(**dict(item)) for item in evidence_rows]
        if not evidence or (not thought.is_open and thought.kind != "unfinished"):
            return ResumptionResponse(
                thought_id=thought.id,
                refined_text=thought.refined_text,
                raw_fragment=thought.raw_fragment,
                where_you_got_to=None,
                supporting_thoughts=[],
                unresolved_loop=None,
                suggested_prompt=None,
                agent_run_id=None,
            )

        correlation_id = uuid4()
        run_id, started = await self._start_run(
            user_id=user_id,
            thought_id=thought_id,
            evidence=evidence,
            correlation_id=correlation_id,
        )
        try:
            output = await self._resume(
                thought_id=thought.id,
                refined_text=thought.refined_text,
                evidence=evidence,
                correlation_id=str(correlation_id),
            )
            await self._succeed_run(run_id=run_id, output=output, started=started)
        except Exception as exc:
            await self._fail_run(run_id=run_id, started=started, error_code=type(exc).__name__)
            raise
        by_id = {item.id: item for item in evidence}
        supporting = [by_id[item] for item in output.result.supporting_thought_ids]
        return ResumptionResponse(
            thought_id=thought.id,
            refined_text=thought.refined_text,
            raw_fragment=thought.raw_fragment,
            where_you_got_to=output.result.where_you_got_to,
            supporting_thoughts=[
                LinkedThoughtView(
                    id=item.id,
                    refined_text=item.refined_text,
                    relation_type=item.relation_type,
                )
                for item in supporting
            ],
            unresolved_loop=output.result.unresolved_loop,
            suggested_prompt=output.result.suggested_prompt,
            agent_run_id=run_id,
        )

    async def _start_run(
        self,
        *,
        user_id: UUID,
        thought_id: UUID,
        evidence: list[ResumptionEvidence],
        correlation_id: UUID,
    ) -> tuple[UUID, float]:
        row = await self._pool.fetchrow(
            """
            insert into public.agent_runs (
                user_id, agent_name, model, schema_version, prompt_version, status,
                input_entity_ids, correlation_id
            )
            values ($1, 'resumption_agent', $2, '1.0', 'resumption-v1', 'running', $3::jsonb, $4)
            returning id
            """,
            user_id,
            self._model,
            [str(thought_id), *[str(item.id) for item in evidence]],
            correlation_id,
        )
        if row is None:
            raise RuntimeError("resumption agent run insert did not return a row")
        return row["id"], monotonic()

    async def _succeed_run(
        self, *, run_id: UUID, output: ResumptionOutput, started: float
    ) -> None:
        latency = max(0, round((monotonic() - started) * 1000))
        await self._pool.execute(
            """
            update public.agent_runs
            set status = 'succeeded', completed_at = now(), latency_ms = $2,
                output_entity_ids = $3::jsonb, openai_trace_id = $4, usage = $5::jsonb
            where id = $1 and status = 'running'
            """,
            run_id,
            latency,
            [str(item) for item in output.result.supporting_thought_ids],
            output.telemetry.trace_id,
            {**output.telemetry.usage, "response_id": output.telemetry.response_id},
        )

    async def _fail_run(
        self, *, run_id: UUID, started: float, error_code: str
    ) -> None:
        latency = max(0, round((monotonic() - started) * 1000))
        await self._pool.execute(
            """
            update public.agent_runs
            set status = 'failed', completed_at = now(), latency_ms = $2,
                error_code = $3, error_message = 'Resumption generation failed'
            where id = $1 and status = 'running'
            """,
            run_id,
            latency,
            error_code,
        )
