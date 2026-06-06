from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import contains_secret_material

CognitiveProviderActivationDecision = Literal["report", "blocked"]
CognitiveProviderActivationScenario = Literal[
    "status",
    "fake-provider-intent",
    "external-provider-block",
    "unsafe-output-block",
]


class CognitiveProviderActivationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

    decision: CognitiveProviderActivationDecision
    target_version: Literal["v3.1.0"] = "v3.1.0"
    release_stage: Literal["intelligence_to_live_execution_platform"] = "intelligence_to_live_execution_platform"
    scenario: CognitiveProviderActivationScenario
    blocked_reasons: tuple[str, ...] = ()
    cognitive_provider_activation_ready: bool = False
    provider_runtime_invoked: bool = False
    cognitive_provider_used: bool = False
    deterministic_fallback_available: bool = True
    intent_frame_validated: bool = False
    goal_intelligence_contract_ready: bool = False
    workloop_bridge_available: bool = False
    capability_grant_required: bool = True
    lease_required: bool = True
    budget_enforced: bool = True
    timeout_required: bool = True
    provider_allowlist_required: bool = True
    output_schema_gate_required: bool = True
    approval_required_for_live: bool = True
    provider_response_contract: Optional[dict[str, JsonValue]] = None
    intent_frame: Optional[dict[str, JsonValue]] = None
    goal_intelligence_contract: Optional[dict[str, JsonValue]] = None
    production_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    authority_widened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> CognitiveProviderActivationContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True)
        return self.model_copy(update={"no_secret_echo": not contains_secret_material(serialized)})
