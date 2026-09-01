from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class WindowLabel(StrEnum):
    FIVE = "5"
    FIFTEEN = "15"
    THIRTY = "30"
    SIXTY = "60"
    A_WHILE = "a_while"


class RetrievalContexts(BaseModel):
    phone_only: bool = False
    out: bool = False
    home: bool = False
    low_energy: bool = False


class RetrievalCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    window: WindowLabel
    contexts: RetrievalContexts = Field(default_factory=RetrievalContexts)
    reshuffle_of: UUID | None = None

    @field_validator("window", mode="before")
    @classmethod
    def normalize_a_while(cls, value: object) -> object:
        return "a_while" if value == "a while" else value


class RetrievalReshuffle(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class RetrievalCard(BaseModel):
    thought_id: UUID
    rank: int
    refined_text: str
    kind: str
    commitment_strength: str
    duration_bucket: str
    energy: str
    contexts: list[str]
    open_loop: dict[str, object]


class RetrievalResponse(BaseModel):
    id: UUID
    window: WindowLabel
    contexts: RetrievalContexts
    reshuffle_of: UUID | None
    candidate_count: int
    ranking_version: str
    cards: list[RetrievalCard]
    created_at: datetime
