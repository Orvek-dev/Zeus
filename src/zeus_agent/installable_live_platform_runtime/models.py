from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import contains_secret_material

InstallableLivePlatformDecision = Literal["report", "blocked"]
InstallableLivePlatformScenario = Literal["status", "plugin-manifest", "remote-sandbox-policy"]


class InstallableLivePlatformContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

    decision: InstallableLivePlatformDecision
    target_version: Literal["v2.3.0"] = "v2.3.0"
    release_stage: Literal["installable_live_platform"] = "installable_live_platform"
    scenario: InstallableLivePlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    installable_live_platform_ready: bool = False
    provider_install_surface_available: bool = False
    mcp_install_surface_available: bool = False
    gateway_install_surface_available: bool = False
    api_install_surface_available: bool = False
    cli_install_surface_available: bool = False
    python_library_install_surface_available: bool = False
    plugin_manifest_install_surface_available: bool = False
    local_sandbox_policy_install_surface_available: bool = False
    remote_sandbox_policy_install_surface_available: bool = False
    live_readiness_contract: Optional[dict[str, JsonValue]] = None
    production_safe_contract: Optional[dict[str, JsonValue]] = None
    plugin_manifest_contract: Optional[dict[str, JsonValue]] = None
    remote_sandbox_policy_contract: Optional[dict[str, JsonValue]] = None
    production_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    remote_sandbox_execution_opened: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> InstallableLivePlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True)
        return self.model_copy(update={"no_secret_echo": not contains_secret_material(serialized)})
