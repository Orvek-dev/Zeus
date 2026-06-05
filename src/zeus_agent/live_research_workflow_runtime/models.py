from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

WorkflowDecision = Literal["workflow_planned", "blocked"]
WorkflowSourceState = Literal["ready_for_policy", "endpoint_required"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowSource(BaseModel):
    model_config = _MODEL_CONFIG

    adapter_id: str
    source_id: str
    display_name: str
    state: WorkflowSourceState
    endpoint: Optional[str]
    endpoint_bound: bool = False
    credential_scope: Optional[str] = None
    required_controls: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()


class LiveResearchWorkflowResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: WorkflowDecision
    plan_id: Optional[str]
    objective_id: str
    query: str
    source_count: int
    ready_source_count: int
    endpoint_required_count: int
    sources: tuple[LiveResearchWorkflowSource, ...]
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
