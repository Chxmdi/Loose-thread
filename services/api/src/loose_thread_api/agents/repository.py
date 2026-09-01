from collections.abc import Mapping
from datetime import datetime
from time import monotonic
from typing import Any
from uuid import UUID

import asyncpg

from loose_thread_api.agents.interpreter import InterpreterOutput
from loose_thread_api.models.jobs import Job


class AgentRunRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def start_interpreter_run(self, *, job: Job, model: str) -> tuple[UUID, float]:
        async with self._pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """
                insert into public.agent_runs (
                    user_id, job_id, agent_name, model, schema_version, prompt_version,
                    status, input_entity_ids, correlation_id
                )
                values ($1, $2, 'thought_interpreter', $3, '1.0', 'interpreter-v1',
                        'running', $4::jsonb, $5)
                returning id
                """,
                job.user_id,
                job.id,
                model,
                [str(job.entity_id)],
                job.correlation_id,
            )
            await connection.execute(
                """
                update public.captures
                set processing_status = 'processing'
                where id = $1 and user_id = $2
                """,
                job.entity_id,
                job.user_id,
            )
        if row is None:
            raise RuntimeError("agent run insert did not return a row")
        return row["id"], monotonic()

    async def succeed_interpreter_run(
        self,
        *,
        run_id: UUID,
        job: Job,
        output: InterpreterOutput,
        started_monotonic: float,
        max_attempts: int,
        client_created_at: datetime,
    ) -> list[UUID]:
        latency_ms = max(0, round((monotonic() - started_monotonic) * 1000))
        thought_ids: list[UUID] = []
        async with self._pool.acquire() as connection, connection.transaction():
            for split_index, thought in enumerate(output.result.thoughts):
                row = await connection.fetchrow(
                    """
                    insert into public.thoughts (
                        user_id, capture_id, split_index, client_created_at, raw_fragment,
                        refined_text, refined_source, kind, commitment_strength,
                        surface_policy, duration_bucket, energy, contexts, entities,
                        temporal, open_loop, confidence, enrichment_version
                    )
                    values (
                        $1, $2, $3, $4, $5, $6, 'model_inferred', $7, $8,
                        $9, $10, $11, $12, $13::jsonb, $14::jsonb, $15::jsonb,
                        $16::jsonb, 'interpreter-v1'
                    )
                    on conflict (capture_id, split_index, enrichment_version) do update
                    set raw_fragment = excluded.raw_fragment,
                        refined_text = excluded.refined_text,
                        refined_source = excluded.refined_source,
                        kind = excluded.kind,
                        commitment_strength = excluded.commitment_strength,
                        surface_policy = excluded.surface_policy,
                        duration_bucket = excluded.duration_bucket,
                        energy = excluded.energy,
                        contexts = excluded.contexts,
                        entities = excluded.entities,
                        temporal = excluded.temporal,
                        open_loop = excluded.open_loop,
                        confidence = excluded.confidence,
                        updated_at = now()
                    returning id
                    """,
                    job.user_id,
                    job.entity_id,
                    split_index,
                    client_created_at,
                    thought.raw_fragment,
                    thought.refined_text,
                    thought.kind.value,
                    thought.commitment_strength.value,
                    thought.surface_policy.value,
                    thought.duration_bucket.value,
                    thought.energy.value,
                    thought.contexts,
                    thought.entities.model_dump(mode="json"),
                    thought.temporal.model_dump(mode="json"),
                    thought.open_loop.model_dump(mode="json"),
                    thought.confidence.model_dump(mode="json"),
                )
                if row is None:
                    raise RuntimeError("thought persistence did not return a row")
                thought_id: UUID = row["id"]
                thought_ids.append(thought_id)
                await connection.execute(
                    """
                    insert into public.jobs (
                        user_id, job_type, entity_type, entity_id, idempotency_key,
                        payload, max_attempts, correlation_id
                    )
                    values ($1, 'embed_thought', 'thought', $2, $3, $4::jsonb, $5, $6)
                    on conflict (user_id, idempotency_key) do nothing
                    """,
                    job.user_id,
                    thought_id,
                    f"embed_thought:{thought_id}:v1",
                    {"thought_id": str(thought_id)},
                    max_attempts,
                    job.correlation_id,
                )

            await connection.execute(
                """
                delete from public.thoughts
                where capture_id = $1 and user_id = $2
                  and enrichment_version = 'interpreter-v1' and split_index >= $3
                """,
                job.entity_id,
                job.user_id,
                len(output.result.thoughts),
            )
            await connection.execute(
                """
                update public.captures
                set processing_status = 'succeeded'
                where id = $1 and user_id = $2
                """,
                job.entity_id,
                job.user_id,
            )
            await connection.execute(
                """
                update public.agent_runs
                set status = 'succeeded', completed_at = now(), latency_ms = $2,
                    output_entity_ids = $3::jsonb, openai_trace_id = $4, usage = $5::jsonb
                where id = $1 and status = 'running'
                """,
                run_id,
                latency_ms,
                [str(thought_id) for thought_id in thought_ids],
                output.telemetry.trace_id,
                {
                    **output.telemetry.usage,
                    "response_id": output.telemetry.response_id,
                },
            )
        return thought_ids

    async def fail_interpreter_run(
        self,
        *,
        run_id: UUID,
        job: Job,
        started_monotonic: float,
        error_code: str,
    ) -> None:
        latency_ms = max(0, round((monotonic() - started_monotonic) * 1000))
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                update public.agent_runs
                set status = 'failed', completed_at = now(), latency_ms = $2,
                    error_code = $3, error_message = 'Thought interpretation failed'
                where id = $1 and status = 'running'
                """,
                run_id,
                latency_ms,
                error_code,
            )
            await connection.execute(
                """
                update public.captures
                set processing_status = 'failed'
                where id = $1 and user_id = $2
                """,
                job.entity_id,
                job.user_id,
            )

    async def list_for_user(
        self, *, user_id: UUID, limit: int = 50
    ) -> list[Mapping[str, Any]]:
        rows = await self._pool.fetch(
            """
            select id, job_id, agent_name, model, schema_version, prompt_version, status,
                   input_entity_ids, output_entity_ids, openai_trace_id, correlation_id,
                   started_at, completed_at, latency_ms, usage, error_code, created_at
            from public.agent_runs
            where user_id = $1
            order by created_at desc
            limit $2
            """,
            user_id,
            max(1, min(limit, 100)),
        )
        return [dict(row) for row in rows]
