from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult
from zeus_agent.live_execute_runtime import LiveExecutePlanResult
from zeus_agent.live_handoff_runtime import LiveHandoffResult
from zeus_agent.live_preflight_runtime import LivePreflightResult
from zeus_agent.live_profile_runtime import LiveProfileResult

LiveDryRunDecision = Literal["planned", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveDryRunResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveDryRunDecision
    surface_id: str
    profile: LiveProfileResult
    approval_receipt: Optional[ApprovalReceiptResult] = None
    preflight: Optional[LivePreflightResult] = None
    handoff: Optional[LiveHandoffResult] = None
    execute_plan: Optional[LiveExecutePlanResult] = None
    blocked_reasons: tuple[str, ...]
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
