from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CaptureMode(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    SHARE = "share"


class CaptureCreate(BaseModel):
    id: UUID
    device_id: UUID
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    capture_mode: CaptureMode
    raw_text: NonEmptyText | None = None
    audio_storage_path: NonEmptyText | None = None
    timezone: NonEmptyText = "UTC"
    client_created_at: datetime

    @model_validator(mode="after")
    def source_matches_mode(self) -> "CaptureCreate":
        if self.capture_mode is CaptureMode.AUDIO and self.audio_storage_path is None:
            raise ValueError("audio_storage_path is required for audio capture")
        if self.capture_mode is not CaptureMode.AUDIO and self.raw_text is None:
            raise ValueError("raw_text is required for text and share captures")
        return self


class CaptureAccepted(BaseModel):
    id: UUID
    processing_status: Literal["queued", "processing", "succeeded", "failed"]
    transcription_status: Literal[
        "not_required", "queued", "processing", "succeeded", "failed"
    ]
    job_id: UUID
    created: bool


class ThoughtView(BaseModel):
    id: UUID
    capture_id: UUID
    split_index: int
    raw_fragment: str
    refined_text: str
    kind: str
    commitment_strength: str
    surface_policy: str
    duration_bucket: str
    energy: str
    contexts: list[str]
    entities: dict[str, list[str]]
    temporal: dict[str, object]
    open_loop: dict[str, object]
    confidence: dict[str, float]
    status: str
    created_at: datetime


class CaptureView(BaseModel):
    id: UUID
    capture_mode: CaptureMode
    raw_text: str | None
    timezone: str
    client_created_at: datetime
    transcription_status: str
    processing_status: str
    created_at: datetime
    thoughts: list[ThoughtView]
