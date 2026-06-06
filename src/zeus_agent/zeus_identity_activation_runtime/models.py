from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ZeusIdentityActivationDecision = Literal["report", "blocked"]
ZeusIdentityActivationScenario = Literal[
    "identity-status",
    "korean-call-smoke",
    "activation-status",
    "activation-check",
]

TARGET_VERSION: Final = "v1.8.0"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.8.0.identity_live_activation"
REQUIRED_ACTIVATION_REQUIREMENTS: Final[tuple[str, ...]] = (
    "objective",
    "runtime_lease",
    "human_approval",
    "credential_binding",
    "sandbox_policy",
    "audit_receipt",
)
SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)


class ZeusIdentityActivationContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ZeusIdentityActivationDecision
    target_version: Literal["v1.8.0"] = TARGET_VERSION
    release_stage: Literal["zeus_identity_live_activation_foundation"] = "zeus_identity_live_activation_foundation"
    objective_contract_id: Literal["zeus.v1.8.0.identity_live_activation"] = OBJECTIVE_CONTRACT_ID
    scenario: ZeusIdentityActivationScenario
    blocked_reasons: tuple[str, ...] = ()
    persona_id: Literal["zeus"] = "zeus"
    display_name: Literal["Zeus"] = "Zeus"
    call_names: tuple[Literal["Zeus"], Literal["제우스"]] = ("Zeus", "제우스")
    default_call_response: Literal["Zeus is here."] = "Zeus is here."
    korean_call_response: Literal["네, 제우스입니다."] = "네, 제우스입니다."
    call_response: Optional[str] = None
    zeus_identity_contract_available: bool = True
    zeus_call_name_runtime_available: bool = True
    live_activation_contract_available: bool = True
    activation_gate_available: bool = True
    objective_requirement_available: bool = True
    lease_requirement_available: bool = True
    approval_requirement_available: bool = True
    credential_binding_requirement_available: bool = True
    sandbox_policy_requirement_available: bool = True
    audit_receipt_requirement_available: bool = True
    activation_requirements: tuple[str, ...] = REQUIRED_ACTIVATION_REQUIREMENTS
    satisfied_activation_requirements: tuple[str, ...] = ()
    missing_activation_requirements: tuple[str, ...] = REQUIRED_ACTIVATION_REQUIREMENTS
    activation_contract_ready: bool = False
    zeus_identity_ready: bool = False
    live_activation_foundation_ready: bool = False
    production_ready: bool = False
    objective_bound: bool = False
    activation_lease_bound: bool = False
    approval_receipt_bound: bool = False
    credential_binding_bound: bool = False
    sandbox_policy_bound: bool = False
    audit_receipt_bound: bool = False
    chat_turn_started: bool = False
    api_server_started: bool = False
    gateway_daemon_started: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    authority_widened: bool = False
    active_rule_written: bool = False
    raw_secret_marker_detected: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ZeusIdentityActivationContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
