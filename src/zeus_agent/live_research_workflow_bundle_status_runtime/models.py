from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

BundleStatusDecision = Literal["bundle_ready", "endpoint_gaps", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowBundleStatusResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: BundleStatusDecision
    status_id: Optional[str]
    bundle_id: Optional[str]
    workflow_plan_id: Optional[str]
    objective_id: str
    source_plan_count: int
    planned_source_count: int
    endpoint_required_count: int
    blocked_source_count: int
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
