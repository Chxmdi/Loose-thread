from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from loose_thread_api.agents.repository import AgentRunRepository
from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.feedback_calibration import FeedbackCalibrationRepository
from loose_thread_api.models.calibration import CalibrationDebugView, FeedbackEventDebugView
from loose_thread_api.models.jobs import JobDebugView
from loose_thread_api.orchestration.repository import JobRepository
from loose_thread_api.retrieval.repository import RetrievalRepository

router = APIRouter(prefix="/v1/debug", tags=["debug"])


class AgentRunDebugView(BaseModel):
    id: UUID
    job_id: UUID | None
    agent_name: str
    model: str
    schema_version: str
    prompt_version: str
    status: str
    input_entity_ids: list[str]
    output_entity_ids: list[str]
    openai_trace_id: str | None
    correlation_id: UUID
    started_at: datetime
    completed_at: datetime | None
    latency_ms: int | None
    usage: dict[str, object]
    error_code: str | None
    created_at: datetime


def get_job_repository(request: Request) -> JobRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return JobRepository(pool)


def get_agent_run_repository(request: Request) -> AgentRunRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return AgentRunRepository(pool)


def get_retrieval_repository(request: Request) -> RetrievalRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return RetrievalRepository(pool)


def get_feedback_calibration_repository(request: Request) -> FeedbackCalibrationRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return FeedbackCalibrationRepository(pool)


@router.get("/jobs", response_model=list[JobDebugView])
async def list_jobs(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[JobRepository, Depends(get_job_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[JobDebugView]:
    jobs = await repository.list_for_user(user_id=current_user.id, limit=limit)
    return [JobDebugView.from_job(job) for job in jobs]


@router.get("/agent-runs", response_model=list[AgentRunDebugView])
async def list_agent_runs(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[AgentRunRepository, Depends(get_agent_run_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AgentRunDebugView]:
    runs = await repository.list_for_user(user_id=current_user.id, limit=limit)
    return [AgentRunDebugView.model_validate(run) for run in runs]


@router.get("/calibration", response_model=CalibrationDebugView)
async def get_calibration(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[
        FeedbackCalibrationRepository,
        Depends(get_feedback_calibration_repository),
    ],
) -> CalibrationDebugView:
    return await repository.get_for_user(user_id=current_user.id)


@router.get("/feedback", response_model=list[FeedbackEventDebugView])
async def list_feedback(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[
        FeedbackCalibrationRepository,
        Depends(get_feedback_calibration_repository),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FeedbackEventDebugView]:
    return await repository.list_feedback_for_user(user_id=current_user.id, limit=limit)


@router.get("/retrievals/{retrieval_id}")
async def get_retrieval_debug(
    retrieval_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[RetrievalRepository, Depends(get_retrieval_repository)],
) -> dict[str, object]:
    debug = await repository.debug_for_user(
        user_id=current_user.id,
        retrieval_id=retrieval_id,
    )
    if debug is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retrieval not found")
    return debug
