from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ThoughtKind(StrEnum):
    TASK = "task"
    IDEA = "idea"
    QUESTION = "question"
    RESEARCH = "research"
    UNFINISHED = "unfinished"
    REMINDER = "reminder"
    OBSERVATION = "observation"
    REFERENCE = "reference"
    FEELING = "feeling"


class CommitmentStrength(StrEnum):
    NONE = "none"
    CURIOSITY = "curiosity"
    POSSIBLE = "possible"
    INTENDED = "intended"
    COMMITTED = "committed"


class DurationBucket(StrEnum):
    SPARK = "spark"
    SNACK = "snack"
    SESSION = "session"
    DEEP = "deep"
    UNKNOWN = "unknown"


class Energy(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class SurfacePolicy(StrEnum):
    NORMAL = "normal"
    RESUMPTION_ONLY = "resumption_only"
    SEARCH_ONLY = "search_only"
    NEVER_PROACTIVE = "never_proactive"


class TemporalType(StrEnum):
    DEADLINE = "deadline"
    NOT_BEFORE = "not_before"
    APPOINTMENT_REFERENCE = "appointment_reference"
    RELATIVE_TIME = "relative_time"
    RECURRENCE_MENTIONED = "recurrence_mentioned"
    UNKNOWN = "unknown"


class Entities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class Temporal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    literal: str | None = None
    type: TemporalType | None = None
    resolved_at: datetime | None = None
    source: Literal["explicit_user_statement"] | None = None


class OpenLoop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_open: bool
    type: str | None = None


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: float = Field(ge=0, le=1)
    commitment_strength: float = Field(ge=0, le=1)
    duration_bucket: float = Field(ge=0, le=1)
    energy: float = Field(ge=0, le=1)
    contexts: float = Field(default=0.5, ge=0, le=1)
    surface_policy: float = Field(ge=0, le=1)


class InterpretedThought(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_fragment: NonEmptyText
    refined_text: NonEmptyText
    kind: ThoughtKind
    commitment_strength: CommitmentStrength
    duration_bucket: DurationBucket
    energy: Energy
    contexts: list[str] = Field(default_factory=list)
    entities: Entities
    temporal: Temporal
    open_loop: OpenLoop
    surface_policy: SurfacePolicy
    confidence: Confidence


class InterpretationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    thoughts: list[InterpretedThought] = Field(max_length=10)
