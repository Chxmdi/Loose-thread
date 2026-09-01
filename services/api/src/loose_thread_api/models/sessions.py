from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from loose_thread_api.models.retrievals import WindowLabel

IdempotencyKey = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class SessionOutcome(StrEnum):
    DONE = "done"
    PARTIAL = "partial"
    STOPPED = "stopped"
    SPAWNED_NEW = "spawned_new"


class FitFeedback(StrEnum):
    SHORTER = "shorter"
    RIGHT = "right"
    LONGER = "longer"


class SessionStart(BaseModel):
    id: UUID
    thought_id: UUID
    retrieval_id: UUID | None = None
    window: WindowLabel
    idempotency_key: IdempotencyKey


class SessionComplete(BaseModel):
    outcome: SessionOutcome
    fit: FitFeedback
    actual_minutes: int | None = None
    idempotency_key: IdempotencyKey


class SessionView(BaseModel):
    id: UUID
    thought_id: UUID
    retrieval_id: UUID | None
    window: WindowLabel
    started_at: datetime
    ended_at: datetime | None
    outcome: SessionOutcome | None
    fit: FitFeedback | None
    actual_minutes: int | None


class SpawnThoughtCreate(BaseModel):
    capture_id: UUID
    thought_id: UUID
    device_id: UUID
    idempotency_key: IdempotencyKey
    raw_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    timezone: str = "UTC"
    client_created_at: datetime


class SpawnThoughtResponse(BaseModel):
    capture_id: UUID
    thought_id: UUID
    spawned_from_thought_id: UUID


class RetrievalAction(StrEnum):
    START = "start"
    NOT_NOW = "not_now"
    DONE_WITH_THIS = "done_with_this"
    NONE_OF_THESE = "none_of_these"


class RetrievalActionCreate(BaseModel):
    action: RetrievalAction
    thought_id: UUID | None = None
    idempotency_key: IdempotencyKey
