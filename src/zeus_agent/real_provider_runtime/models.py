from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealProviderDecision = Literal["report", "blocked"]
RealProviderScenario = Literal[
    "status",
    "blocked-missing-opt-in",
    "blocked-unallowlisted",
    "blocked-budget",
    "local-deterministic-smoke",
    "external-receipt-smoke",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
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
    "-----begin",
)


class RealProviderProfile(BaseModel):
    model_config = _MODEL_CONFIG

    provider_id: str
    display_name: str
    api_mode: str
    default_model: str
    runtime_kind: str
    network_host: Optional[str] = None
    credential_scope: Optional[str] = None
    local_first: bool = False
    tool_calling: bool = False
    streaming: bool = False
    structured_output: bool = False
    vision: bool = False
    embeddings: bool = False
    live_beta: bool = False


class RealProviderContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealProviderDecision
    target_version: Literal["v1.1.0"]
    release_stage: Literal["real_provider_runtime"]
    objective_contract_id: Literal["zeus.v1.1.0.real_provider_runtime"]
    scenario: RealProviderScenario
    blocked_reasons: tuple[str, ...] = ()
    real_provider_runtime_contract_available: bool = True
    provider_profiles_available: bool = True
    local_llm_profile_available: bool = False
    openai_compatible_profile_available: bool = False
    governed_external_provider_available: bool = False
    local_provider_smoke_available: bool = True
    real_provider_runtime_ready: bool = False
    local_provider_ready: bool = False
    external_provider_ready: bool = False
    production_ready: bool = False
    provider_profile_count: int = 0
    provider_profiles: tuple[RealProviderProfile, ...] = ()
    budget_limit: int = 0
    budget_requested: int = 0
    budget_approved: bool = False
    timeout_ms: int = 0
    operator_live_opted_in: bool = False
    endpoint_allowlisted: bool = False
    secret_material_available: bool = False
    local_smoke: Optional[dict[str, JsonValue]] = None
    external_smoke: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    provider_invoked: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealProviderContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
