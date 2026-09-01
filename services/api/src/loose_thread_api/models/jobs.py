from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    DEAD_LETTER = "dead_letter"


class JobType(StrEnum):
    TRANSCRIBE_CAPTURE = "transcribe_capture"
    INTERPRET_CAPTURE = "interpret_capture"
    EMBED_THOUGHT = "embed_thought"
    LINK_THOUGHT = "link_thought"
    BUILD_RESUMPTION_CONTEXT = "build_resumption_context"
    APPLY_FEEDBACK_CALIBRATION = "apply_feedback_calibration"
    CLEANUP_EXPIRED_AUDIO = "cleanup_expired_audio"


class Job(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID
    job_type: JobType
    entity_type: str
    entity_id: UUID
    status: JobStatus
    priority: int
    attempts: int
    max_attempts: int
    run_after: datetime
    locked_at: datetime | None
    locked_by: str | None
    lease_expires_at: datetime | None
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_version: int
    correlation_id: UUID
    last_error_code: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Job":
        return cls.model_validate(dict(record))


class JobDebugView(BaseModel):
    id: UUID
    job_type: JobType
    entity_type: str
    entity_id: UUID
    status: JobStatus
    attempts: int
    max_attempts: int
    run_after: datetime
    locked_at: datetime | None
    lease_expires_at: datetime | None
    correlation_id: UUID
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: Job) -> "JobDebugView":
        return cls.model_validate(job, from_attributes=True)
