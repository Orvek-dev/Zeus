from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

McpOwnedClientLiveDecision = Literal["report", "blocked"]
McpOwnedClientLiveScenario = Literal[
    "status",
    "blocked-missing-opt-in",
    "blocked-missing-secret",
    "owned-client-smoke",
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
    "private-key",
    "-----begin",
)


class McpOwnedClientLiveContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: McpOwnedClientLiveDecision
    target_version: str
    release_stage: Literal["mcp_owned_client_live"]
    objective_contract_id: str
    scenario: McpOwnedClientLiveScenario
    blocked_reasons: tuple[str, ...] = ()
    mcp_owned_client_live_contract_available: bool = True
    mcp_owned_client_transport_available: bool = True
    mcp_owned_client_adapter_available: bool = True
    remote_transport_policy_available: bool = True
    remote_executor_preflight_available: bool = True
    remote_credential_handoff_available: bool = True
    mcp_owned_client_live_ready: bool = False
    production_ready: bool = False
    operator_live_opted_in: bool = False
    endpoint_allowlisted: bool = False
    secret_material_available: bool = False
    mcp_owned_client_smoke: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    tool_invoked: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    raw_secret_returned: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> McpOwnedClientLiveContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
