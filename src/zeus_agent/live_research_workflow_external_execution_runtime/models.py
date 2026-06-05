from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowExternalExecutionDecision = Literal["external_execution_recorded", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExternalExecutionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExternalExecutionDecision
    execution_id: Optional[str]
    execution_record_ref: Optional[str]
    preflight_id: Optional[str]
    preflight_ref: Optional[str]
    external_execution_ref: Optional[str]
    external_transport_execution_id: Optional[str]
    owned_client_execution_id: Optional[str] = None
    handoff_manifest_id: Optional[str]
    policy_id: Optional[str]
    source_id: Optional[str]
    source_pin_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    workflow_external_preflight_bound: bool = False
    external_result_bound: bool = False
    owned_client_result_bound: bool = False
    policy_bound: bool = False
    source_pin_bound: bool = False
    research_invoked: bool = False
    live_search_enabled: bool = False
    execution_allowed: bool = False
    external_transport_executed: bool = False
    external_network_seen: bool = False
    external_non_loopback_network_seen: bool = False
    external_cleanup_receipt_bound: bool = False
    controlled_external_side_effects_seen: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: Optional[int] = None
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
