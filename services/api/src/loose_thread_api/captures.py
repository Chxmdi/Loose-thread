from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from loose_thread_api.models.captures import CaptureAccepted, CaptureCreate, CaptureView
from loose_thread_api.models.jobs import JobType


class CaptureConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptureForInterpretation:
    id: UUID
    user_id: UUID
    raw_text: str
    timezone: str
    client_created_at: datetime


class CaptureRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_with_job(
        self,
        *,
        user_id: UUID,
        capture: CaptureCreate,
        max_attempts: int,
    ) -> CaptureAccepted:
        correlation_id = uuid4()
        transcription_status = (
            "queued" if capture.capture_mode.value == "audio" else "not_required"
        )
        job_type = (
            JobType.TRANSCRIBE_CAPTURE
            if capture.capture_mode.value == "audio"
            else JobType.INTERPRET_CAPTURE
        )
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                capture_row = await connection.fetchrow(
                    """
                    insert into public.captures (
                        id, user_id, device_id, idempotency_key, capture_mode, raw_text,
                        audio_storage_path, timezone, client_created_at, transcription_status
                    )
                    values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    on conflict (user_id, idempotency_key) do nothing
                    returning id, processing_status, transcription_status
                    """,
                    capture.id,
                    user_id,
                    capture.device_id,
                    capture.idempotency_key,
                    capture.capture_mode.value,
                    capture.raw_text,
                    capture.audio_storage_path,
                    capture.timezone,
                    capture.client_created_at,
                    transcription_status,
                )
                created = capture_row is not None
                if capture_row is None:
                    capture_row = await connection.fetchrow(
                        """
                        select id, processing_status, transcription_status
                        from public.captures
                        where user_id = $1 and idempotency_key = $2
                        """,
                        user_id,
                        capture.idempotency_key,
                    )
                if capture_row is None:
                    raise RuntimeError("capture insert did not return a row")

                capture_id = capture_row["id"]
                job_row = await connection.fetchrow(
                    """
                    insert into public.jobs (
                        user_id, job_type, entity_type, entity_id, idempotency_key,
                        payload, max_attempts, correlation_id
                    )
                    values ($1, $2, 'capture', $3, $4, $5::jsonb, $6, $7)
                    on conflict (user_id, idempotency_key) do update
                    set idempotency_key = public.jobs.idempotency_key
                    returning id
                    """,
                    user_id,
                    job_type.value,
                    capture_id,
                    f"{job_type.value}:{capture_id}:v1",
                    {"capture_id": str(capture_id)},
                    max_attempts,
                    correlation_id,
                )
        except asyncpg.UniqueViolationError as exc:
            raise CaptureConflictError("capture id is already in use") from exc

        if job_row is None:
            raise RuntimeError("capture job insert did not return a row")
        return CaptureAccepted(
            id=capture_row["id"],
            processing_status=capture_row["processing_status"],
            transcription_status=capture_row["transcription_status"],
            job_id=job_row["id"],
            created=created,
        )

    async def get_for_user(self, *, user_id: UUID, capture_id: UUID) -> CaptureView | None:
        capture_row = await self._pool.fetchrow(
            """
            select id, capture_mode, raw_text, timezone, client_created_at,
                   transcription_status, processing_status, created_at
            from public.captures
            where id = $1 and user_id = $2 and not is_deleted
            """,
            capture_id,
            user_id,
        )
        if capture_row is None:
            return None
        thought_rows = await self._pool.fetch(
            """
            select id, capture_id, split_index, raw_fragment, refined_text, kind,
                   commitment_strength, surface_policy, duration_bucket, energy,
                   contexts, entities, temporal, open_loop, confidence, status, created_at
            from public.thoughts
            where capture_id = $1 and user_id = $2 and not is_deleted
            order by split_index
            """,
            capture_id,
            user_id,
        )
        payload: dict[str, Any] = dict(capture_row)
        payload["thoughts"] = [dict(row) for row in thought_rows]
        return CaptureView.model_validate(payload)

    async def get_for_interpretation(
        self, *, user_id: UUID, capture_id: UUID
    ) -> CaptureForInterpretation | None:
        row = await self._pool.fetchrow(
            """
            select id, user_id, raw_text, timezone, client_created_at
            from public.captures
            where id = $1 and user_id = $2 and not is_deleted
            """,
            capture_id,
            user_id,
        )
        if row is None or row["raw_text"] is None:
            return None
        return CaptureForInterpretation(**dict(row))
