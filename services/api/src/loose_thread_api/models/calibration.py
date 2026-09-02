from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CalibrationDebugView(BaseModel):
    duration_calibration: dict[str, float] = Field(default_factory=dict)
    kind_affinity: dict[str, float] = Field(default_factory=dict)
    context_affinity: dict[str, float] = Field(default_factory=dict)
    observation_count: int = 0
    updated_at: datetime | None = None


class FeedbackEventDebugView(BaseModel):
    id: UUID
    session_id: UUID | None
    retrieval_id: UUID | None
    thought_id: UUID | None
    event_type: str
    event_data: dict[str, Any] = Field(default_factory=dict)
    calibration_applied_at: datetime | None
    calibration_version: str | None
    created_at: datetime
