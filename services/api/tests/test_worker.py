from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from loose_thread_api.models.jobs import Job, JobStatus, JobType
from loose_thread_api.orchestration.repository import JobRepository
from loose_thread_api.orchestration.worker import JobHandlerError, Worker


def make_running_job() -> Job:
    now = datetime.now(UTC)
    return Job(
        id=uuid4(),
        user_id=uuid4(),
        job_type=JobType.INTERPRET_CAPTURE,
        entity_type="capture",
        entity_id=uuid4(),
        status=JobStatus.RUNNING,
        priority=100,
        attempts=1,
        max_attempts=5,
        run_after=now,
        locked_at=now,
        locked_by="worker-a",
        lease_expires_at=now,
        idempotency_key="interpret:test:v1",
        payload={},
        payload_version=1,
        correlation_id=uuid4(),
        last_error_code=None,
        last_error=None,
        created_at=now,
        updated_at=now,
    )


class FakeRepository:
    def __init__(self, job: Job) -> None:
        self.job = job
        self.completed = False
        self.failed = False

    async def claim(self, *, worker_id: str, limit: int, lease_seconds: int) -> list[Job]:
        del worker_id, limit, lease_seconds
        return [self.job]

    async def complete(self, *, job_id: object, worker_id: str) -> Job:
        del job_id, worker_id
        self.completed = True
        return self.job.model_copy(update={"status": JobStatus.SUCCEEDED})

    async def fail(
        self,
        *,
        job_id: object,
        worker_id: str,
        error_code: str,
        error_message: str,
        retry_delay_seconds: int,
        retryable: bool,
    ) -> Job:
        del job_id, worker_id, error_code, error_message, retry_delay_seconds, retryable
        self.failed = True
        return self.job.model_copy(update={"status": JobStatus.RETRY_WAIT})


async def test_worker_completes_successful_handler() -> None:
    job = make_running_job()
    repository = FakeRepository(job)
    handled: list[object] = []

    async def handler(current_job: Job) -> None:
        handled.append(current_job.id)

    worker = Worker(
        repository=cast(JobRepository, repository),
        worker_id="worker-a",
        handlers={JobType.INTERPRET_CAPTURE: handler},
        lease_seconds=60,
    )

    assert await worker.run_once() == 1
    assert handled == [job.id]
    assert repository.completed
    assert not repository.failed


async def test_worker_persists_handler_failure() -> None:
    job = make_running_job()
    repository = FakeRepository(job)

    async def handler(current_job: Job) -> None:
        del current_job
        raise JobHandlerError("model_timeout", "Model timed out")

    worker = Worker(
        repository=cast(JobRepository, repository),
        worker_id="worker-a",
        handlers={JobType.INTERPRET_CAPTURE: handler},
        lease_seconds=60,
    )

    assert await worker.run_once() == 1
    assert repository.failed
    assert not repository.completed
