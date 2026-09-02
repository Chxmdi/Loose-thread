import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping

from loose_thread_api.models.jobs import Job, JobType
from loose_thread_api.orchestration.backoff import retry_delay
from loose_thread_api.orchestration.repository import JobOwnershipError, JobRepository

JobHandler = Callable[[Job], Awaitable[None]]


class JobHandlerError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class Worker:
    def __init__(
        self,
        *,
        repository: JobRepository,
        worker_id: str,
        handlers: Mapping[JobType, JobHandler],
        lease_seconds: int,
        concurrency: int = 4,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._worker_id = worker_id
        self._handlers = handlers
        self._lease_seconds = lease_seconds
        self._concurrency = max(1, min(concurrency, 32))
        self._logger = logger or logging.getLogger("loose_thread.worker")

    async def run_once(self) -> int:
        jobs = await self._repository.claim(
            worker_id=self._worker_id,
            limit=self._concurrency,
            lease_seconds=self._lease_seconds,
        )
        if not jobs:
            return 0
        await asyncio.gather(*(self._run_job(job) for job in jobs))
        return len(jobs)

    async def run_forever(self, *, poll_seconds: float, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                processed = await self.run_once()
            except Exception as exc:
                self._logger.exception(
                    "worker_poll_failed",
                    extra={
                        "worker_id": self._worker_id,
                        "error_code": type(exc).__name__,
                    },
                )
                await self._wait_for_poll(poll_seconds, stop_event)
                continue
            if processed:
                continue
            await self._wait_for_poll(poll_seconds, stop_event)

    @staticmethod
    async def _wait_for_poll(poll_seconds: float, stop_event: asyncio.Event) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.1, poll_seconds))
        except TimeoutError:
            pass

    async def _run_job(self, job: Job) -> None:
        handler = self._handlers.get(job.job_type)
        if handler is None:
            await self._record_failure(
                job,
                JobHandlerError(
                    "handler_missing",
                    f"No handler registered for {job.job_type.value}",
                    retryable=False,
                ),
            )
            return

        self._logger.info(
            "job_started",
            extra={
                "job_id": str(job.id),
                "job_type": job.job_type.value,
                "user_id": str(job.user_id),
                "correlation_id": str(job.correlation_id),
                "attempt": job.attempts,
            },
        )
        try:
            await handler(job)
            await self._repository.complete(job_id=job.id, worker_id=self._worker_id)
        except JobHandlerError as exc:
            await self._record_failure(job, exc)
        # A worker boundary must turn unknown handler failures into durable retry state.
        except Exception as exc:  # noqa: BLE001
            await self._record_failure(
                job,
                JobHandlerError(
                    type(exc).__name__,
                    "Unhandled job handler failure",
                    retryable=True,
                ),
            )
        else:
            self._logger.info(
                "job_succeeded",
                extra={
                    "job_id": str(job.id),
                    "job_type": job.job_type.value,
                    "user_id": str(job.user_id),
                    "correlation_id": str(job.correlation_id),
                    "attempt": job.attempts,
                },
            )

    async def _record_failure(self, job: Job, error: JobHandlerError) -> None:
        delay = retry_delay(job.attempts, job.idempotency_key)
        try:
            failed = await self._repository.fail(
                job_id=job.id,
                worker_id=self._worker_id,
                error_code=error.code,
                error_message=str(error),
                retry_delay_seconds=int(delay.total_seconds()),
                retryable=error.retryable,
            )
        except JobOwnershipError:
            self._logger.warning(
                "job_lease_lost",
                extra={
                    "job_id": str(job.id),
                    "job_type": job.job_type.value,
                    "user_id": str(job.user_id),
                    "correlation_id": str(job.correlation_id),
                },
            )
            return
        self._logger.warning(
            "job_failed",
            extra={
                "job_id": str(job.id),
                "job_type": job.job_type.value,
                "user_id": str(job.user_id),
                "correlation_id": str(job.correlation_id),
                "attempt": job.attempts,
                "status": failed.status.value,
                "error_code": error.code,
            },
        )
