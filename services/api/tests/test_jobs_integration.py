import asyncio
import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.config import Settings
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.main import create_app
from loose_thread_api.models.jobs import JobStatus, JobType
from loose_thread_api.orchestration.repository import JobRepository

USER_A = UUID("11111111-1111-4111-8111-111111111111")
USER_B = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for Postgres integration tests")

    pool = await create_database_pool(database_url)
    await pool.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [USER_A, USER_B],
    )
    await pool.execute(
        """
        insert into auth.users (id, email)
        values ($1, 'jobs-a@example.test'), ($2, 'jobs-b@example.test')
        """,
        USER_A,
        USER_B,
    )
    try:
        yield pool
    finally:
        await pool.execute(
            "delete from auth.users where id = any($1::uuid[])",
            [USER_A, USER_B],
        )
        await pool.close()


async def test_atomic_claims_never_duplicate_work(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    for index in range(10):
        await repository.enqueue(
            user_id=USER_A,
            job_type=JobType.INTERPRET_CAPTURE,
            entity_type="capture",
            entity_id=uuid4(),
            idempotency_key=f"claim:{index}",
        )

    first, second = await asyncio.gather(
        repository.claim(worker_id="worker-a", limit=10, lease_seconds=60),
        repository.claim(worker_id="worker-b", limit=10, lease_seconds=60),
    )

    claimed_ids = [job.id for job in first + second]
    assert len(claimed_ids) == 10
    assert len(set(claimed_ids)) == 10
    assert {job.locked_by for job in first + second} <= {"worker-a", "worker-b"}


async def test_duplicate_enqueue_returns_the_original_job(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    entity_id = uuid4()

    first = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.EMBED_THOUGHT,
        entity_type="thought",
        entity_id=entity_id,
        idempotency_key=f"embed:{entity_id}",
    )
    duplicate = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.EMBED_THOUGHT,
        entity_type="thought",
        entity_id=entity_id,
        idempotency_key=f"embed:{entity_id}",
    )

    assert duplicate.id == first.id


async def test_retry_then_dead_letter_at_max_attempts(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    queued = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        idempotency_key="retry-to-dead-letter",
        max_attempts=2,
    )

    first_claim = (await repository.claim(worker_id="worker-a", limit=1, lease_seconds=60))[0]
    assert first_claim.id == queued.id
    first_failure = await repository.fail(
        job_id=queued.id,
        worker_id="worker-a",
        error_code="model_timeout",
        error_message="Model timed out",
        retry_delay_seconds=0,
        retryable=True,
    )
    assert first_failure.status is JobStatus.RETRY_WAIT

    second_claim = (await repository.claim(worker_id="worker-a", limit=1, lease_seconds=60))[0]
    second_failure = await repository.fail(
        job_id=second_claim.id,
        worker_id="worker-a",
        error_code="model_timeout",
        error_message="Model timed out again",
        retry_delay_seconds=0,
        retryable=True,
    )
    assert second_failure.status is JobStatus.DEAD_LETTER
    assert second_failure.attempts == 2


async def test_expired_lease_can_be_recovered(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    queued = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        idempotency_key="expired-lease",
    )
    first_claim = (await repository.claim(worker_id="worker-a", limit=1, lease_seconds=60))[0]
    assert first_claim.id == queued.id

    await database_pool.execute(
        "update public.jobs set lease_expires_at = now() - interval '1 second' where id = $1",
        queued.id,
    )
    recovered = (await repository.claim(worker_id="worker-b", limit=1, lease_seconds=60))[0]

    assert recovered.id == queued.id
    assert recovered.locked_by == "worker-b"
    assert recovered.attempts == 2


async def test_final_expired_lease_moves_to_dead_letter(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    queued = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        idempotency_key="expired-final-lease",
        max_attempts=1,
    )
    claimed = (await repository.claim(worker_id="worker-a", limit=1, lease_seconds=60))[0]
    assert claimed.id == queued.id

    await database_pool.execute(
        "update public.jobs set lease_expires_at = now() - interval '1 second' where id = $1",
        queued.id,
    )
    assert await repository.claim(worker_id="worker-b", limit=1, lease_seconds=60) == []
    row = await database_pool.fetchrow("select * from public.jobs where id = $1", queued.id)

    assert row is not None
    assert row["status"] == JobStatus.DEAD_LETTER.value
    assert row["last_error_code"] == "lease_expired_at_max_attempts"


async def test_job_debug_endpoint_is_user_scoped(database_pool: asyncpg.Pool) -> None:
    repository = JobRepository(database_pool)
    own_job = await repository.enqueue(
        user_id=USER_A,
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        idempotency_key="debug-own",
    )
    await repository.enqueue(
        user_id=USER_B,
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        idempotency_key="debug-other",
    )

    database_url = os.environ["DATABASE_URL"]
    app = create_app(Settings(database_url=database_url))

    async def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_A, is_anonymous=True)

    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        response = client.get("/v1/debug/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [str(own_job.id)]
