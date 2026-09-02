import asyncio
import logging
import os
import socket

import asyncpg

from loose_thread_api.agents.continuity import ContinuityAgent
from loose_thread_api.agents.handler import InterpretationJobHandler
from loose_thread_api.agents.interpreter import ThoughtInterpreter
from loose_thread_api.agents.repository import AgentRunRepository
from loose_thread_api.captures import CaptureRepository
from loose_thread_api.config import Settings, get_settings
from loose_thread_api.continuity_handlers import ContinuityJobHandler, EmbeddingJobHandler
from loose_thread_api.continuity_repository import ContinuityRepository
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.embeddings import EmbeddingService
from loose_thread_api.feedback_calibration import (
    FeedbackCalibrationJobHandler,
    FeedbackCalibrationRepository,
)
from loose_thread_api.models.jobs import JobType
from loose_thread_api.orchestration.repository import JobRepository
from loose_thread_api.orchestration.worker import JobHandler, Worker


def get_handlers(pool: asyncpg.Pool, settings: Settings) -> dict[JobType, JobHandler]:
    interpreter = ThoughtInterpreter(settings)
    embedding_service = EmbeddingService(settings)
    continuity_agent = ContinuityAgent(settings)
    continuity_repository = ContinuityRepository(pool)
    feedback_calibration_repository = FeedbackCalibrationRepository(pool)
    return {
        JobType.INTERPRET_CAPTURE: InterpretationJobHandler(
            captures=CaptureRepository(pool),
            agent_runs=AgentRunRepository(pool),
            interpret=interpreter.interpret,
            model=settings.openai_model_interpreter,
            max_attempts=settings.job_max_attempts,
        ),
        JobType.EMBED_THOUGHT: EmbeddingJobHandler(
            repository=continuity_repository,
            embed=embedding_service.embed,
            max_attempts=settings.job_max_attempts,
        ),
        JobType.LINK_THOUGHT: ContinuityJobHandler(
            repository=continuity_repository,
            relate=continuity_agent.relate,
            model=settings.openai_model_continuity,
            candidate_limit=settings.continuity_candidate_limit,
        ),
        JobType.APPLY_FEEDBACK_CALIBRATION: FeedbackCalibrationJobHandler(
            feedback_calibration_repository
        ),
    }


async def run_worker() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required to run the worker")

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    pool = await create_database_pool(settings.database_url.get_secret_value())
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    worker = Worker(
        repository=JobRepository(pool),
        worker_id=worker_id,
        handlers=get_handlers(pool, settings),
        lease_seconds=settings.job_lease_seconds,
        concurrency=settings.worker_concurrency,
    )
    stop_event = asyncio.Event()
    try:
        await worker.run_forever(
            poll_seconds=settings.job_poll_seconds,
            stop_event=stop_event,
        )
    finally:
        await pool.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
