from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResumptionAgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    where_you_got_to: str = Field(min_length=1, max_length=500)
    supporting_thought_ids: list[UUID] = Field(min_length=1, max_length=3)
    unresolved_loop: str | None = Field(default=None, max_length=300)
    suggested_prompt: str | None = Field(default=None, max_length=200)


class LinkedThoughtView(BaseModel):
    id: UUID
    refined_text: str
    relation_type: str


class ResumptionResponse(BaseModel):
    thought_id: UUID
    refined_text: str
    raw_fragment: str
    where_you_got_to: str | None
    supporting_thoughts: list[LinkedThoughtView]
    unresolved_loop: str | None
    suggested_prompt: str | None
    agent_run_id: UUID | None
