from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from loose_thread_api.agents.resumption import ResumptionAgent
from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.config import Settings
from loose_thread_api.models.resumption import ResumptionResponse
from loose_thread_api.resumption_service import ResumptionService

router = APIRouter(prefix="/v1/thoughts", tags=["thoughts"])


def get_resumption_service(request: Request) -> ResumptionService:
    pool = getattr(request.app.state, "database_pool", None)
    if not isinstance(pool, asyncpg.Pool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    settings = getattr(request.app.state, "settings", Settings())
    try:
        agent = ResumptionAgent(settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resumption is not configured",
        ) from exc
    return ResumptionService(
        pool,
        resume=agent.resume,
        model=settings.openai_model_resumption,
    )


@router.get("/{thought_id}/resumption", response_model=ResumptionResponse)
async def get_resumption(
    thought_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ResumptionService, Depends(get_resumption_service)],
) -> ResumptionResponse:
    try:
        response = await service.get(user_id=current_user.id, thought_id=thought_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resumption generation failed",
        ) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thought not found")
    return response
