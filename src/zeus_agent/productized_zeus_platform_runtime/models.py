from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import contains_secret_material

ProductizedZeusPlatformDecision = Literal["report", "blocked"]
ProductizedZeusPlatformScenario = Literal[
    "status",
    "zeus-persona",
    "setup-status",
    "cockpit",
    "operator-map",
    "plugin-tenant-learning",
    "public-boundary",
]


@dataclass(frozen=True)
class ProductizedZeusPayloads:
    setup: dict[str, JsonValue]
    cognitive: dict[str, JsonValue]
    product: dict[str, JsonValue]
    scale: dict[str, JsonValue]

    def to_contract_parts(self) -> dict[str, dict[str, JsonValue]]:
        return {
            "setup_plan": self.setup,
            "cognitive_contract": self.cognitive,
            "product_platform_contract": self.product,
            "production_scale_contract": self.scale,
        }


class ProductizedZeusPlatformContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

    decision: ProductizedZeusPlatformDecision
    target_version: Literal["v4.0.0"] = "v4.0.0"
    release_stage: Literal["productized_zeus_platform"] = "productized_zeus_platform"
    objective_contract_id: Literal["zeus.v4.0.0.productized_zeus_platform"] = (
        "zeus.v4.0.0.productized_zeus_platform"
    )
    scenario: ProductizedZeusPlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    productized_zeus_platform_ready: bool = False
    zeus_persona_ready: bool = False
    setup_wizard_ready: bool = False
    status_cockpit_ready: bool = False
    operator_command_map_ready: bool = False
    cognitive_provider_activation_ready: bool = False
    plugin_ecosystem_ready: bool = False
    tenant_auth_ready: bool = False
    candidate_learning_ready: bool = False
    public_boundary_ready: bool = False
    installable_user_journey_ready: bool = False
    zeus_call_response: Literal["네, 제우스입니다."] = "네, 제우스입니다."
    setup_plan: Optional[dict[str, JsonValue]] = None
    cognitive_contract: Optional[dict[str, JsonValue]] = None
    product_platform_contract: Optional[dict[str, JsonValue]] = None
    production_scale_contract: Optional[dict[str, JsonValue]] = None
    operator_commands: tuple[str, ...] = ()
    operator_command_count: int = 0
    production_ready: bool = False
    production_live_ready: bool = False
    unrestricted_live_execution_enabled: bool = False
    external_provider_enabled: bool = False
    mcp_remote_server_enabled: bool = False
    external_gateway_delivery_enabled: bool = False
    browser_live_execution_enabled: bool = False
    remote_sandbox_execution_enabled: bool = False
    unattended_execution_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    authority_widened: bool = False
    active_rule_written: bool = False
    live_production_claimed: bool = False
    settings_written: bool = False
    raw_secret_marker_detected: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ProductizedZeusPlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True)
        safe = not contains_secret_material(serialized)
        return self.model_copy(update={"no_secret_echo": safe})
