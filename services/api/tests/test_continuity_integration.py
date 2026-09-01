import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from loose_thread_api.agents.continuity import (
    ContinuityAgent,
    ContinuityCandidate,
    ContinuityOutput,
    ContinuityTelemetry,
)
from loose_thread_api.continuity_handlers import ContinuityJobHandler, EmbeddingJobHandler
from loose_thread_api.continuity_repository import ContinuityRepository
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.embeddings import EmbeddingOutput
from loose_thread_api.models.continuity import (
    ContinuityResult,
    ProposedRelationship,
    RelationType,
)
from loose_thread_api.models.jobs import JobType
from loose_thread_api.orchestration.repository import JobRepository
from loose_thread_api.orchestration.worker import JobHandlerError

USER_A = UUID("66666666-6666-4666-8666-666666666666")
USER_B = UUID("77777777-7777-4777-8777-777777777777")
DIMENSIONS = 1536


@pytest.fixture
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for Postgres integration tests")
    pool = await create_database_pool(database_url)
    await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
    await pool.execute(
        """
        insert into auth.users (id, email)
        values ($1, 'continuity-a@example.test'), ($2, 'continuity-b@example.test')
        """,
        USER_A,
        USER_B,
    )
    try:
        yield pool
    finally:
        await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
        await pool.close()


def vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second, *([0.0] * (DIMENSIONS - 2))]


async def insert_thought(
    pool: asyncpg.Pool,
    *,
    user_id: UUID,
    text: str,
    embedding: list[float] | None,
) -> UUID:
    capture_id = uuid4()
    thought_id = uuid4()
    await pool.execute(
        """
        insert into public.captures (
            id, user_id, device_id, idempotency_key, capture_mode, raw_text,
            timezone, client_created_at, processing_status
        )
        values ($1, $2, $3, $4, 'text', $5, 'UTC', $6, 'succeeded')
        """,
        capture_id,
        user_id,
        uuid4(),
        f"test:{capture_id}",
        text,
        datetime.now(UTC),
    )
    await pool.execute(
        """
        insert into public.thoughts (
            id, user_id, capture_id, split_index, client_created_at, raw_fragment,
            refined_text, refined_source, kind, commitment_strength, surface_policy,
            duration_bucket, energy, entities, temporal, open_loop, confidence, embedding
        )
        values (
            $1, $2, $3, 0, $4, $5, $5, 'user_raw', 'task', 'intended', 'normal',
            'snack', 'medium', '{}', '{}', '{"is_open": true}', '{}', $6
        )
        """,
        thought_id,
        user_id,
        capture_id,
        datetime.now(UTC),
        text,
        embedding,
    )
    return thought_id


def continuity_output(
    *, source_id: UUID, target_id: UUID | None = None
) -> ContinuityOutput:
    relationships = []
    if target_id is not None:
        relationships.append(
            ProposedRelationship(
                from_thought_id=source_id,
                to_thought_id=target_id,
                relation_type=RelationType.CONTINUES,
                confidence=0.91,
                rationale="The new thought directly advances the earlier open loop.",
            )
        )
    return ContinuityOutput(
        result=ContinuityResult(relationships=relationships),
        telemetry=ContinuityTelemetry(
            trace_id="trace_abcdefabcdefabcdefabcdefabcdefab",
            response_id="resp_continuity_test",
            usage={"requests": 1, "input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
        ),
    )


async def test_embedding_is_persisted_and_link_job_is_enqueued(
    database_pool: asyncpg.Pool,
) -> None:
    thought_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Plan the launch email",
        embedding=None,
    )
    jobs = JobRepository(database_pool)
    await jobs.enqueue(
        user_id=USER_A,
        job_type=JobType.EMBED_THOUGHT,
        entity_type="thought",
        entity_id=thought_id,
        idempotency_key=f"embed_thought:{thought_id}:v1",
    )
    job = (await jobs.claim(worker_id="embedding-test", limit=1, lease_seconds=60))[0]

    async def fake_embed(_: str) -> EmbeddingOutput:
        return EmbeddingOutput(
            vector=vector(1.0),
            model="test-embedding",
            usage={"prompt_tokens": 3, "total_tokens": 3},
        )

    handler = EmbeddingJobHandler(
        repository=ContinuityRepository(database_pool),
        embed=fake_embed,
        max_attempts=5,
    )
    await handler(job)
    await jobs.complete(job_id=job.id, worker_id="embedding-test")

    dimensions = await database_pool.fetchval(
        "select extensions.vector_dims(embedding) from public.thoughts where id = $1",
        thought_id,
    )
    link_jobs = await database_pool.fetchval(
        "select count(*) from public.jobs where entity_id = $1 and job_type = 'link_thought'",
        thought_id,
    )
    assert dimensions == DIMENSIONS
    assert link_jobs == 1


async def test_vector_candidates_are_bounded_and_cross_user_is_impossible(
    database_pool: asyncpg.Pool,
) -> None:
    source_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Continue the launch email",
        embedding=vector(1.0),
    )
    own_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Draft the launch email",
        embedding=vector(0.99, 0.01),
    )
    await insert_thought(
        database_pool,
        user_id=USER_B,
        text="Another user's near-identical private thought",
        embedding=vector(1.0),
    )

    loaded = await ContinuityRepository(database_pool).load_source_and_candidates(
        user_id=USER_A,
        thought_id=source_id,
        limit=1,
    )
    assert loaded is not None
    _, candidates = loaded
    assert [candidate.id for candidate in candidates] == [own_id]


async def test_relevant_neighbor_is_linked_idempotently_and_run_is_audited(
    database_pool: asyncpg.Pool,
) -> None:
    source_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="I finished the launch email draft",
        embedding=vector(1.0),
    )
    target_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Draft the launch email",
        embedding=vector(0.98, 0.02),
    )
    jobs = JobRepository(database_pool)
    await jobs.enqueue(
        user_id=USER_A,
        job_type=JobType.LINK_THOUGHT,
        entity_type="thought",
        entity_id=source_id,
        idempotency_key=f"link_thought:{source_id}:v1",
    )
    job = (await jobs.claim(worker_id="continuity-test", limit=1, lease_seconds=60))[0]

    async def fake_relate(**kwargs: object) -> ContinuityOutput:
        candidates = kwargs["candidates"]
        assert isinstance(candidates, list)
        assert all(isinstance(candidate, ContinuityCandidate) for candidate in candidates)
        return continuity_output(source_id=source_id, target_id=target_id)

    handler = ContinuityJobHandler(
        repository=ContinuityRepository(database_pool),
        relate=fake_relate,
        model="test-model",
        candidate_limit=8,
    )
    await handler(job)
    await handler(job)
    await jobs.complete(job_id=job.id, worker_id="continuity-test")

    relationship_count = await database_pool.fetchval(
        """
        select count(*) from public.thought_relationships
        where from_thought_id = $1 and to_thought_id = $2 and relation_type = 'continues'
        """,
        source_id,
        target_id,
    )
    run_count = await database_pool.fetchval(
        "select count(*) from public.agent_runs where job_id = $1 and status = 'succeeded'",
        job.id,
    )
    assert relationship_count == 1
    assert run_count == 2


async def test_unrelated_candidate_produces_no_relation_and_failure_remains_retryable(
    database_pool: asyncpg.Pool,
) -> None:
    source_id = await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Outline a recipe",
        embedding=vector(1.0),
    )
    await insert_thought(
        database_pool,
        user_id=USER_A,
        text="Renew the parking permit",
        embedding=vector(0.0, 1.0),
    )
    jobs = JobRepository(database_pool)
    await jobs.enqueue(
        user_id=USER_A,
        job_type=JobType.LINK_THOUGHT,
        entity_type="thought",
        entity_id=source_id,
        idempotency_key=f"link_thought:{source_id}:v1",
    )
    job = (await jobs.claim(worker_id="continuity-test", limit=1, lease_seconds=60))[0]

    async def no_relation(**_: object) -> ContinuityOutput:
        return continuity_output(source_id=source_id)

    repository = ContinuityRepository(database_pool)
    handler = ContinuityJobHandler(
        repository=repository,
        relate=no_relation,
        model="test-model",
        candidate_limit=8,
    )
    await handler(job)
    assert await database_pool.fetchval(
        "select count(*) from public.thought_relationships where from_thought_id = $1",
        source_id,
    ) == 0

    async def model_failure(**_: object) -> ContinuityOutput:
        raise RuntimeError("provider unavailable")

    failing_handler = ContinuityJobHandler(
        repository=repository,
        relate=model_failure,
        model="test-model",
        candidate_limit=8,
    )
    with pytest.raises(JobHandlerError):
        await failing_handler(job)
    assert await database_pool.fetchval(
        "select refined_text from public.thoughts where id = $1",
        source_id,
    ) == "Outline a recipe"


def test_continuity_rejects_unsupplied_candidate_id() -> None:
    source_id = uuid4()
    supplied_id = uuid4()
    result = continuity_output(source_id=source_id, target_id=uuid4()).result
    candidates = [
        ContinuityCandidate(
            id=supplied_id,
            refined_text="Supplied",
            kind="task",
            commitment_strength="intended",
            created_at="2026-09-01T12:00:00Z",
            similarity=0.9,
        )
    ]
    with pytest.raises(ValueError, match="unsupplied"):
        ContinuityAgent._validate_ids(source_id, candidates, result)
