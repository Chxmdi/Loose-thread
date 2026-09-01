from uuid import UUID

from loose_thread_api.models.jobs import Job, JobType
from loose_thread_api.orchestration.repository import JobRepository


async def enqueue_capture_processing(
    repository: JobRepository,
    *,
    user_id: UUID,
    capture_id: UUID,
    requires_transcription: bool,
    correlation_id: UUID,
    max_attempts: int,
) -> Job:
    job_type = (
        JobType.TRANSCRIBE_CAPTURE if requires_transcription else JobType.INTERPRET_CAPTURE
    )
    return await repository.enqueue(
        user_id=user_id,
        job_type=job_type,
        entity_type="capture",
        entity_id=capture_id,
        idempotency_key=f"{job_type.value}:{capture_id}:v1",
        payload={"capture_id": str(capture_id)},
        correlation_id=correlation_id,
        max_attempts=max_attempts,
    )


async def enqueue_thought_enrichment(
    repository: JobRepository,
    *,
    user_id: UUID,
    thought_id: UUID,
    correlation_id: UUID,
    max_attempts: int,
) -> Job:
    return await repository.enqueue(
        user_id=user_id,
        job_type=JobType.EMBED_THOUGHT,
        entity_type="thought",
        entity_id=thought_id,
        idempotency_key=f"embed_thought:{thought_id}:v1",
        payload={"thought_id": str(thought_id)},
        correlation_id=correlation_id,
        max_attempts=max_attempts,
    )


async def enqueue_thought_linking(
    repository: JobRepository,
    *,
    user_id: UUID,
    thought_id: UUID,
    correlation_id: UUID,
    max_attempts: int,
) -> Job:
    return await repository.enqueue(
        user_id=user_id,
        job_type=JobType.LINK_THOUGHT,
        entity_type="thought",
        entity_id=thought_id,
        idempotency_key=f"link_thought:{thought_id}:v1",
        payload={"thought_id": str(thought_id)},
        correlation_id=correlation_id,
        max_attempts=max_attempts,
    )
