from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RelationType(StrEnum):
    CONTINUES = "continues"
    ELABORATES = "elaborates"
    ANSWERS = "answers"
    CONTRADICTS = "contradicts"
    REFERENCES = "references"
    SPAWNED_FROM = "spawned_from"
    SAME_TOPIC = "same_topic"
    SAME_PERSON = "same_person"
    SAME_PROJECT = "same_project"


class ProposedRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_thought_id: UUID
    to_thought_id: UUID
    relation_type: RelationType
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=500)


class ContinuityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationships: list[ProposedRelationship] = Field(max_length=8)
