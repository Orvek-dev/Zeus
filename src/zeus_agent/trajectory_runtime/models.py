from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

JsonObject = dict[str, JsonValue]


class TrajectoryExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    run_id: str
    events: tuple[JsonObject, ...]
    event_count: int = Field(ge=0)
    redacted: bool
    live_production_claimed: bool = False
