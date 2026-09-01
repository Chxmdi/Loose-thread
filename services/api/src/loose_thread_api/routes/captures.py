from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.captures import CaptureConflictError, CaptureRepository
from loose_thread_api.config import Settings
from loose_thread_api.models.captures import CaptureAccepted, CaptureCreate, CaptureView

router = APIRouter(prefix="/v1/captures", tags=["captures"])


def get_capture_repository(request: Request) -> CaptureRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return CaptureRepository(pool)


@router.post("", response_model=CaptureAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_capture(
    capture: CaptureCreate,
    request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[CaptureRepository, Depends(get_capture_repository)],
) -> CaptureAccepted:
    settings = getattr(request.app.state, "settings", Settings())
    try:
        return await repository.create_with_job(
            user_id=current_user.id,
            capture=capture,
            max_attempts=settings.job_max_attempts,
        )
    except CaptureConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{capture_id}", response_model=CaptureView)
async def get_capture(
    capture_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[CaptureRepository, Depends(get_capture_repository)],
) -> CaptureView:
    capture = await repository.get_for_user(user_id=current_user.id, capture_id=capture_id)
    if capture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture not found")
    return capture
