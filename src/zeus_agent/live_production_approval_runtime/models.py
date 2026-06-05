from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_transport_audit_runtime.execution_rules import LiveTransportAdapterKind

LiveProductionApprovalDecision = Literal["production_approval_ready", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveProductionApprovalResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProductionApprovalDecision
    production_approval_id: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    execution_id: Optional[str]
    audit_id: Optional[str]
    teardown_id: Optional[str]
    approval_receipt_id: Optional[str]
    operator_proof_id: Optional[str]
    production_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    execution_bound: bool = False
    audit_bound: bool = False
    teardown_bound: bool = False
    approval_receipt_bound: bool = False
    operator_proof_bound: bool = False
    required_risks_acknowledged: bool = False
    controlled_external_side_effects: bool = False
    production_claim_authorized: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
