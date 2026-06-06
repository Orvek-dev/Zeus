from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ProductionSafeLivePlatformDecision = Literal["report", "blocked"]
ProductionSafeLivePlatformScenario = Literal[
    "status",
    "provider-mcp-smoke",
    "platform-execution-boundary",
    "activation-required-block",
]

TARGET_VERSION: Final = "v1.9.0"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.9.0.production_safe_live_platform_connections"
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
CONNECTOR_MAP: Final[tuple[str, ...]] = (
    "external_ai_provider",
    "mcp_server",
    "hosted_api",
    "gateway_daemon",
    "browser_live_navigation",
    "terminal_sandbox",
    "remote_sandbox",
)

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)


class ProductionSafeLivePlatformContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ProductionSafeLivePlatformDecision
    target_version: Literal["v1.9.0"] = TARGET_VERSION
    release_stage: Literal["production_safe_live_platform_connections"] = "production_safe_live_platform_connections"
    objective_contract_id: Literal["zeus.v1.9.0.production_safe_live_platform_connections"] = OBJECTIVE_CONTRACT_ID
    scenario: ProductionSafeLivePlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    connector_map: tuple[str, ...] = CONNECTOR_MAP
    connection_surface_count: int = len(CONNECTOR_MAP)
    blocked_surface_count: int = 0
    production_safe_live_platform_contract_available: bool = True
    live_connector_activation_layer_available: bool = True
    external_provider_connection_available: bool = True
    mcp_production_connection_available: bool = True
    hosted_api_connection_available: bool = True
    gateway_daemon_connection_available: bool = True
    browser_live_connection_available: bool = True
    terminal_sandbox_connection_available: bool = True
    remote_sandbox_connection_available: bool = True
    production_safe_connections_ready: bool = False
    provider_connection_ready: bool = False
    mcp_connection_ready: bool = False
    platform_connection_ready: bool = False
    platform_boundary_ready: bool = False
    execution_boundary_ready: bool = False
    production_ready: bool = False
    activation_contract: Optional[dict[str, JsonValue]] = None
    provider_contract: Optional[dict[str, JsonValue]] = None
    mcp_contract: Optional[dict[str, JsonValue]] = None
    platform_contract: Optional[dict[str, JsonValue]] = None
    execution_contract: Optional[dict[str, JsonValue]] = None
    gateway_boundary_contract: Optional[dict[str, JsonValue]] = None
    browser_boundary_contract: Optional[dict[str, JsonValue]] = None
    remote_sandbox_boundary_contract: Optional[dict[str, JsonValue]] = None
    chat_turn_started: bool = False
    api_server_started: bool = False
    gateway_daemon_started: bool = False
    browser_navigation_opened: bool = False
    remote_sandbox_opened: bool = False
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

    def with_secret_scan(self) -> ProductionSafeLivePlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
