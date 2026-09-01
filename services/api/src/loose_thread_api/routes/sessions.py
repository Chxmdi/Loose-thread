from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.models.sessions import (
    SessionComplete,
    SessionStart,
    SessionView,
    SpawnThoughtCreate,
    SpawnThoughtResponse,
)
from loose_thread_api.sessions_repository import SessionConflictError, SessionRepository

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def get_session_repository(request: Request) -> SessionRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return SessionRepository(pool)


@router.post("", response_model=SessionView, status_code=status.HTTP_201_CREATED)
async def start_session(
    body: SessionStart,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> SessionView:
    try:
        return await repository.start(user_id=current_user.id, body=body)
    except SessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{session_id}/complete", response_model=SessionView)
async def complete_session(
    session_id: UUID,
    body: SessionComplete,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> SessionView:
    try:
        return await repository.complete(user_id=current_user.id, session_id=session_id, body=body)
    except SessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{session_id}/spawn", response_model=SpawnThoughtResponse)
async def spawn_thought(
    session_id: UUID,
    body: SpawnThoughtCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> SpawnThoughtResponse:
    try:
        return await repository.spawn(user_id=current_user.id, session_id=session_id, body=body)
    except SessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
