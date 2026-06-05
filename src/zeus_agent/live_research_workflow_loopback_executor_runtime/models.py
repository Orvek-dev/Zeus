from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

WorkflowLoopbackExecutorDecision = Literal["loopback_executed", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowLoopbackExecutorResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: WorkflowLoopbackExecutorDecision
    workflow_execution_id: Optional[str]
    handoff_manifest_id: Optional[str]
    handoff_ref: Optional[str]
    execution_ref: str
    adapter_id: Optional[str]
    source_id: Optional[str]
    endpoint: Optional[str]
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: Optional[int] = None
    cleanup_receipt: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    handoff_bound: bool = False
    execution_plan_bound: bool = False
    loopback_smoke_bound: bool = False
    execution_allowed: bool = False
    client_constructed: bool = False
    research_invoked: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
