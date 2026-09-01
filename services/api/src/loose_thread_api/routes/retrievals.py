from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.config import Settings
from loose_thread_api.models.retrievals import (
    RetrievalCreate,
    RetrievalReshuffle,
    RetrievalResponse,
)
from loose_thread_api.models.sessions import RetrievalActionCreate
from loose_thread_api.retrieval.engine import RetrievalEngine
from loose_thread_api.retrieval.repository import RetrievalConflictError, RetrievalRepository
from loose_thread_api.sessions_repository import SessionConflictError, SessionRepository

router = APIRouter(prefix="/v1/retrievals", tags=["retrievals"])


def get_retrieval_repository(request: Request) -> RetrievalRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return RetrievalRepository(pool)


def get_retrieval_engine(request: Request) -> RetrievalEngine:
    settings = getattr(request.app.state, "settings", Settings())
    return RetrievalEngine(
        weights=settings.retrieval_weights(),
        minimum_score=settings.retrieval_minimum_score,
    )


def get_session_repository(request: Request) -> SessionRepository:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return SessionRepository(pool)


@router.post("", response_model=RetrievalResponse, status_code=status.HTTP_201_CREATED)
async def create_retrieval(
    body: RetrievalCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[RetrievalRepository, Depends(get_retrieval_repository)],
    engine: Annotated[RetrievalEngine, Depends(get_retrieval_engine)],
) -> RetrievalResponse:
    try:
        return await repository.create(user_id=current_user.id, request=body, engine=engine)
    except RetrievalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/{retrieval_id}/reshuffle",
    response_model=RetrievalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reshuffle_retrieval(
    retrieval_id: UUID,
    body: RetrievalReshuffle,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[RetrievalRepository, Depends(get_retrieval_repository)],
    engine: Annotated[RetrievalEngine, Depends(get_retrieval_engine)],
) -> RetrievalResponse:
    try:
        return await repository.create_reshuffle(
            user_id=current_user.id,
            retrieval_id=retrieval_id,
            new_id=body.id,
            engine=engine,
        )
    except RetrievalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{retrieval_id}/action", status_code=status.HTTP_204_NO_CONTENT)
async def record_retrieval_action(
    retrieval_id: UUID,
    body: RetrievalActionCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> None:
    try:
        await repository.record_retrieval_action(
            user_id=current_user.id,
            retrieval_id=retrieval_id,
            body=body,
        )
    except SessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
