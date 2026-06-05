from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowExternalPreflightDecision = Literal["external_preflight_ready", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExternalPreflightResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExternalPreflightDecision
    preflight_id: Optional[str]
    preflight_ref: Optional[str]
    external_execution_ref: Optional[str]
    handoff_manifest_id: Optional[str]
    handoff_ref: Optional[str]
    policy_id: Optional[str]
    source_id: Optional[str]
    source_pin_ref: Optional[str]
    operator_approval_ref: Optional[str]
    evidence_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    workflow_handoff_bound: bool = False
    policy_bound: bool = False
    approval_bound: bool = False
    evidence_bound: bool = False
    source_pin_bound: bool = False
    live_search_allowed: bool = False
    execution_allowed: bool = False
    external_transport_allowed: bool = False
    operator_review_required: bool = True
    live_transport_enabled: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
