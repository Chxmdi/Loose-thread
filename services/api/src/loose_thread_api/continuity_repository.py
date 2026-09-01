from dataclasses import dataclass
from time import monotonic
from typing import Any
from uuid import UUID

import asyncpg

from loose_thread_api.agents.continuity import (
    ContinuityCandidate,
    ContinuityOutput,
)
from loose_thread_api.embeddings import EmbeddingOutput
from loose_thread_api.models.jobs import Job


@dataclass(frozen=True)
class ThoughtForContinuity:
    id: UUID
    refined_text: str
    kind: str
    commitment_strength: str
    embedding: Any


class ContinuityRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_thought_text(self, *, user_id: UUID, thought_id: UUID) -> str | None:
        value = await self._pool.fetchval(
            """
            select refined_text
            from public.thoughts
            where id = $1 and user_id = $2 and not is_deleted
            """,
            thought_id,
            user_id,
        )
        return value if isinstance(value, str) else None

    async def save_embedding_and_enqueue_link(
        self,
        *,
        job: Job,
        output: EmbeddingOutput,
        max_attempts: int,
    ) -> None:
        async with self._pool.acquire() as connection, connection.transaction():
            result = await connection.execute(
                """
                update public.thoughts
                set embedding = $3, enrichment = enrichment || $4::jsonb, updated_at = now()
                where id = $1 and user_id = $2 and not is_deleted
                """,
                job.entity_id,
                job.user_id,
                output.vector,
                {"embedding_model": output.model, "embedding_usage": output.usage},
            )
            if result != "UPDATE 1":
                raise ValueError("thought is missing or unavailable for embedding")
            await connection.execute(
                """
                insert into public.jobs (
                    user_id, job_type, entity_type, entity_id, idempotency_key,
                    payload, max_attempts, correlation_id
                )
                values ($1, 'link_thought', 'thought', $2, $3, $4::jsonb, $5, $6)
                on conflict (user_id, idempotency_key) do nothing
                """,
                job.user_id,
                job.entity_id,
                f"link_thought:{job.entity_id}:v1",
                {"thought_id": str(job.entity_id)},
                max_attempts,
                job.correlation_id,
            )

    async def load_source_and_candidates(
        self,
        *,
        user_id: UUID,
        thought_id: UUID,
        limit: int,
    ) -> tuple[ThoughtForContinuity, list[ContinuityCandidate]] | None:
        source = await self._pool.fetchrow(
            """
            select id, refined_text, kind, commitment_strength, embedding
            from public.thoughts
            where id = $1 and user_id = $2 and embedding is not null and not is_deleted
            """,
            thought_id,
            user_id,
        )
        if source is None:
            return None
        source_thought = ThoughtForContinuity(**dict(source))
        rows = await self._pool.fetch(
            """
            select id, refined_text, kind, commitment_strength, created_at,
                   1 - (embedding <=> $3) as similarity
            from public.thoughts
            where user_id = $1 and id <> $2 and embedding is not null and not is_deleted
            order by embedding <=> $3, created_at desc, id
            limit $4
            """,
            user_id,
            thought_id,
            source_thought.embedding,
            max(1, min(limit, 20)),
        )
        candidates = [
            ContinuityCandidate(
                id=row["id"],
                refined_text=row["refined_text"],
                kind=row["kind"],
                commitment_strength=row["commitment_strength"],
                created_at=row["created_at"].isoformat(),
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]
        return source_thought, candidates

    async def start_agent_run(self, *, job: Job, model: str) -> tuple[UUID, float]:
        row = await self._pool.fetchrow(
            """
            insert into public.agent_runs (
                user_id, job_id, agent_name, model, schema_version, prompt_version,
                status, input_entity_ids, correlation_id
            )
            values ($1, $2, 'continuity_agent', $3, '1.0', 'continuity-v1',
                    'running', $4::jsonb, $5)
            returning id
            """,
            job.user_id,
            job.id,
            model,
            [str(job.entity_id)],
            job.correlation_id,
        )
        if row is None:
            raise RuntimeError("continuity agent run insert did not return a row")
        return row["id"], monotonic()

    async def succeed_agent_run(
        self,
        *,
        run_id: UUID,
        job: Job,
        output: ContinuityOutput | None,
        candidate_ids: set[UUID],
        started_monotonic: float,
    ) -> list[UUID]:
        latency_ms = max(0, round((monotonic() - started_monotonic) * 1000))
        relationship_ids: list[UUID] = []
        async with self._pool.acquire() as connection, connection.transaction():
            if output is not None:
                for relationship in output.result.relationships:
                    if (
                        relationship.from_thought_id != job.entity_id
                        or relationship.to_thought_id not in candidate_ids
                    ):
                        raise ValueError("relationship references an invalid thought")
                    row = await connection.fetchrow(
                        """
                        insert into public.thought_relationships (
                            user_id, from_thought_id, to_thought_id, relation_type,
                            confidence, source, rationale, model_version
                        )
                        values ($1, $2, $3, $4, $5, 'model', $6, 'continuity-v1')
                        on conflict (from_thought_id, to_thought_id, relation_type) do update
                        set confidence = excluded.confidence,
                            rationale = excluded.rationale,
                            model_version = excluded.model_version
                        returning id
                        """,
                        job.user_id,
                        relationship.from_thought_id,
                        relationship.to_thought_id,
                        relationship.relation_type.value,
                        relationship.confidence,
                        relationship.rationale,
                    )
                    if row is None:
                        raise RuntimeError("relationship persistence did not return a row")
                    relationship_ids.append(row["id"])

            trace_id = output.telemetry.trace_id if output is not None else None
            usage: dict[str, object] = dict(output.telemetry.usage) if output is not None else {}
            if output is not None:
                usage = {**usage, "response_id": output.telemetry.response_id}
            await connection.execute(
                """
                update public.agent_runs
                set status = 'succeeded', completed_at = now(), latency_ms = $2,
                    output_entity_ids = $3::jsonb, openai_trace_id = $4, usage = $5::jsonb
                where id = $1 and status = 'running'
                """,
                run_id,
                latency_ms,
                [str(item) for item in relationship_ids],
                trace_id,
                usage,
            )
        return relationship_ids

    async def fail_agent_run(
        self,
        *,
        run_id: UUID,
        started_monotonic: float,
        error_code: str,
    ) -> None:
        latency_ms = max(0, round((monotonic() - started_monotonic) * 1000))
        await self._pool.execute(
            """
            update public.agent_runs
            set status = 'failed', completed_at = now(), latency_ms = $2,
                error_code = $3, error_message = 'Continuity analysis failed'
            where id = $1 and status = 'running'
            """,
            run_id,
            latency_ms,
            error_code,
        )
