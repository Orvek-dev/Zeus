from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

LiveCredentialInjectionDecision = Literal["injection_ready", "blocked"]
LiveCredentialInjectionAdapterKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveCredentialInjectionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveCredentialInjectionDecision
    injection_id: Optional[str]
    adapter_kind: Optional[LiveCredentialInjectionAdapterKind]
    claim_id: Optional[str]
    production_approval_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    handoff_id: Optional[str]
    material_proof_id: Optional[str]
    remote_target_identity: Optional[str]
    credential_scope: Optional[str]
    secret_ref: Optional[str]
    injection_ref: Optional[str]
    header_name: Optional[str]
    header_value_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    production_claim_bound: bool = False
    policy_bound: bool = False
    preflight_bound: bool = False
    credential_handoff_bound: bool = False
    secret_material_bound: bool = False
    endpoint_binding_verified: bool = False
    material_access_proof_bound: bool = False
    sealed_header_ref_ready: bool = False
    credential_injection_ready: bool = False
    secret_material_env_read_confirmed: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
