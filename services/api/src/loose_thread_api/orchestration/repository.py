from collections.abc import Mapping
from typing import Any
from uuid import UUID

import asyncpg

from loose_thread_api.models.jobs import Job, JobType


class JobOwnershipError(RuntimeError):
    pass


class JobRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def enqueue(
        self,
        *,
        user_id: UUID,
        job_type: JobType,
        entity_type: str,
        entity_id: UUID,
        idempotency_key: str,
        payload: Mapping[str, Any] | None = None,
        payload_version: int = 1,
        priority: int = 100,
        max_attempts: int = 5,
        correlation_id: UUID | None = None,
    ) -> Job:
        row = await self._pool.fetchrow(
            """
            insert into public.jobs (
                user_id,
                job_type,
                entity_type,
                entity_id,
                idempotency_key,
                payload,
                payload_version,
                priority,
                max_attempts,
                correlation_id
            )
            values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, coalesce($10, gen_random_uuid()))
            on conflict (user_id, idempotency_key) do update
            set idempotency_key = public.jobs.idempotency_key
            returning public.jobs.*
            """,
            user_id,
            job_type.value,
            entity_type,
            entity_id,
            idempotency_key,
            dict(payload or {}),
            payload_version,
            priority,
            max_attempts,
            correlation_id,
        )
        if row is None:
            raise RuntimeError("job enqueue did not return a row")
        return Job.from_record(row)

    async def claim(self, *, worker_id: str, limit: int, lease_seconds: int) -> list[Job]:
        rows = await self._pool.fetch(
            "select * from private.claim_jobs($1, $2, $3)",
            worker_id,
            limit,
            lease_seconds,
        )
        return [Job.from_record(row) for row in rows]

    async def complete(self, *, job_id: UUID, worker_id: str) -> Job:
        row = await self._pool.fetchrow(
            "select * from private.complete_job($1, $2)",
            job_id,
            worker_id,
        )
        if row is None or row["id"] is None:
            raise JobOwnershipError("job is not owned by this worker")
        return Job.from_record(row)

    async def fail(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        error_code: str,
        error_message: str,
        retry_delay_seconds: int,
        retryable: bool,
    ) -> Job:
        row = await self._pool.fetchrow(
            "select * from private.fail_job($1, $2, $3, $4, $5, $6)",
            job_id,
            worker_id,
            error_code,
            error_message,
            retry_delay_seconds,
            retryable,
        )
        if row is None or row["id"] is None:
            raise JobOwnershipError("job is not owned by this worker")
        return Job.from_record(row)

    async def renew_lease(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> Job:
        row = await self._pool.fetchrow(
            "select * from private.renew_job_lease($1, $2, $3)",
            job_id,
            worker_id,
            lease_seconds,
        )
        if row is None or row["id"] is None:
            raise JobOwnershipError("job lease is no longer owned by this worker")
        return Job.from_record(row)

    async def list_for_user(self, *, user_id: UUID, limit: int = 50) -> list[Job]:
        rows = await self._pool.fetch(
            """
            select *
            from public.jobs
            where user_id = $1
            order by created_at desc
            limit $2
            """,
            user_id,
            max(1, min(limit, 100)),
        )
        return [Job.from_record(row) for row in rows]
