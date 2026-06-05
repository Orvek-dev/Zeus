from __future__ import annotations

import json
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, JsonValue

StableReleaseDecision = Literal["report", "blocked"]

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


class StableReleaseContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: StableReleaseDecision
    target_version: Literal["v1.0.0"]
    release_stage: Literal["stable_governed_live_platform"]
    objective_contract_id: Literal["zeus.v1.0.0.stable_governed_live_platform"]
    blocked_reasons: tuple[str, ...] = ()
    stable_release_ready: bool = False
    governed_live_platform_ready: bool = False
    stable_public_release_ready: bool = False
    production_live_ready: bool = False
    unrestricted_live_execution_enabled: bool = False
    provider_live_api_available: bool = True
    mcp_live_server_available: bool = True
    gateway_live_delivery_available: bool = True
    sandbox_terminal_live_available: bool = True
    memory_privacy_live_available: bool = True
    provider_live_optin_available: bool = True
    provider_owned_client_live_available: bool = True
    mcp_owned_client_live_available: bool = True
    mcp_resources_enabled: bool = False
    mcp_prompts_enabled: bool = False
    external_gateway_production_enabled: bool = False
    browser_live_execution_enabled: bool = False
    remote_sandbox_execution_enabled: bool = False
    unattended_execution_enabled: bool = False
    raw_secret_marker_detected: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> StableReleaseContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
