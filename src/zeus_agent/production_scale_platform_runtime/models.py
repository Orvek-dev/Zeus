from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import contains_secret_material

ProductionScalePlatformDecision = Literal["report", "blocked"]
ProductionScalePlatformScenario = Literal[
    "status",
    "plugin-ecosystem",
    "remote-sandbox-policy",
    "tenant-auth-contract",
    "learning-ops",
]


class ProductionScalePlatformContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

    decision: ProductionScalePlatformDecision
    target_version: Literal["v2.4.0"] = "v2.4.0"
    release_stage: Literal["production_scale_platform"] = "production_scale_platform"
    scenario: ProductionScalePlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    production_scale_platform_ready: bool = False
    plugin_ecosystem_available: bool = False
    plugin_manifest_validation_available: bool = False
    plugin_permission_policy_available: bool = False
    plugin_quarantine_available: bool = False
    remote_sandbox_backend_interface_available: bool = False
    docker_backend_policy_available: bool = False
    ssh_backend_policy_available: bool = False
    network_egress_default_denied: bool = False
    mount_allowlist_required: bool = False
    credential_passthrough_default_denied: bool = False
    eval_registry_available: bool = False
    error_ledger_available: bool = False
    promotion_review_available: bool = False
    candidate_only_learning_available: bool = False
    tenant_model_available: bool = False
    principal_model_available: bool = False
    api_key_auth_contract_available: bool = False
    role_scope_enforcement_available: bool = False
    tenant_isolation_contract_available: bool = False
    persistent_audit_contract_available: bool = False
    installable_live_platform_contract: Optional[dict[str, JsonValue]] = None
    plugin_ecosystem_contract: Optional[dict[str, JsonValue]] = None
    remote_sandbox_policy_contract: Optional[dict[str, JsonValue]] = None
    learning_ops_contract: Optional[dict[str, JsonValue]] = None
    tenant_auth_contract: Optional[dict[str, JsonValue]] = None
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

    def with_secret_scan(self) -> ProductionScalePlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True)
        return self.model_copy(update={"no_secret_echo": not contains_secret_material(serialized)})
