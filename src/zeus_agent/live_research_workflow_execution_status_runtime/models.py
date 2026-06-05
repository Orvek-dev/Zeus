from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowExecutionStatusDecision = Literal["execution_recorded", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExecutionStatusResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExecutionStatusDecision
    status_id: Optional[str]
    status_ref: str
    evidence_ref: Optional[str]
    workflow_execution_id: Optional[str]
    execution_kind: Optional[Literal["loopback", "external"]] = None
    external_execution_id: Optional[str] = None
    external_transport_execution_id: Optional[str] = None
    external_preflight_ref: Optional[str] = None
    handoff_manifest_id: Optional[str]
    handoff_ref: Optional[str]
    adapter_id: Optional[str]
    source_id: Optional[str]
    result_count: int = 0
    blocked_reasons: tuple[str, ...] = ()
    loopback_executor_bound: bool = False
    external_execution_bound: bool = False
    evidence_bound: bool = False
    operator_review_required: bool = True
    loopback_network_seen: bool = False
    external_network_seen: bool = False
    external_non_loopback_network_seen: bool = False
    non_loopback_network_opened: bool = False
    production_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
