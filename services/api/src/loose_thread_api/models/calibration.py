from datetime import datetime

from pydantic import BaseModel, Field


class CalibrationDebugView(BaseModel):
    duration_calibration: dict[str, float] = Field(default_factory=dict)
    kind_affinity: dict[str, float] = Field(default_factory=dict)
    context_affinity: dict[str, float] = Field(default_factory=dict)
    observation_count: int = 0
    updated_at: datetime | None = None
