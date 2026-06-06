from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.installable_live_platform_runtime import build_installable_live_platform_contract
from zeus_agent.plugin_runtime import validate_plugin_manifest
from zeus_agent.production_scale_platform_runtime.models import ProductionScalePlatformContract
from zeus_agent.production_scale_platform_runtime.models import ProductionScalePlatformDecision
from zeus_agent.production_scale_platform_runtime.models import ProductionScalePlatformScenario
from zeus_agent.security.credentials import contains_secret_material

_SAFE_PLUGIN_MANIFEST: Final[dict[str, JsonValue]] = {
    "plugin_id": "zeus.scale_local",
    "name": "Scale Local Plugin",
    "version": "0.1.0",
    "entrypoint": "plugins/scale_local.py",
    "permissions": ["tool.read", "memory.read", "wiki.read"],
    "dependencies": ["pydantic"],
    "sha256": "b" * 64,
}


def build_production_scale_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    operator_note: Optional[str] = None,
) -> ProductionScalePlatformContract:
    if operator_note is not None and contains_secret_material(operator_note):
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("raw_secret_marker_detected",),
        )
    parsed = _parse_scenario(scenario)
    if parsed is None:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_production_scale_platform_scenario",),
        )
    if parsed == "plugin-ecosystem":
        return _plugin_ecosystem_contract()
    if parsed == "remote-sandbox-policy":
        return _remote_sandbox_policy_contract()
    if parsed == "tenant-auth-contract":
        return _tenant_auth_contract()
    if parsed == "learning-ops":
        return _learning_ops_contract()
    return _status_contract(home=home)


def _status_contract(*, home: Optional[Path]) -> ProductionScalePlatformContract:
    installable = _json_payload(build_installable_live_platform_contract(
        scenario="status",
        home=home,
    ).to_payload())
    plugin = _plugin_ecosystem_payload()
    remote = _remote_sandbox_policy_payload()
    learning = _learning_ops_payload()
    tenant = _tenant_auth_payload()
    ready = installable["decision"] == "report" and plugin["decision"] == "quarantined"
    return _contract(
        decision="report" if ready else "blocked",
        scenario="status",
        blocked_reasons=() if ready else ("production_scale_surface_unavailable",),
        production_scale_platform_ready=ready,
        installable_live_platform_contract=installable,
        plugin_ecosystem_contract=plugin,
        remote_sandbox_policy_contract=remote,
        learning_ops_contract=learning,
        tenant_auth_contract=tenant,
    )


def _plugin_ecosystem_contract() -> ProductionScalePlatformContract:
    return _contract(
        decision="report",
        scenario="plugin-ecosystem",
        plugin_ecosystem_contract=_plugin_ecosystem_payload(),
    )


def _remote_sandbox_policy_contract() -> ProductionScalePlatformContract:
    return _contract(
        decision="blocked",
        scenario="remote-sandbox-policy",
        blocked_reasons=("remote_sandbox_default_denied",),
        remote_sandbox_policy_contract=_remote_sandbox_policy_payload(),
    )


def _tenant_auth_contract() -> ProductionScalePlatformContract:
    return _contract(
        decision="report",
        scenario="tenant-auth-contract",
        tenant_auth_contract=_tenant_auth_payload(),
    )


def _learning_ops_contract() -> ProductionScalePlatformContract:
    return _contract(
        decision="report",
        scenario="learning-ops",
        learning_ops_contract=_learning_ops_payload(),
    )


def _contract(
    *,
    decision: ProductionScalePlatformDecision,
    scenario: ProductionScalePlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    production_scale_platform_ready: bool = False,
    installable_live_platform_contract: Optional[dict[str, JsonValue]] = None,
    plugin_ecosystem_contract: Optional[dict[str, JsonValue]] = None,
    remote_sandbox_policy_contract: Optional[dict[str, JsonValue]] = None,
    learning_ops_contract: Optional[dict[str, JsonValue]] = None,
    tenant_auth_contract: Optional[dict[str, JsonValue]] = None,
) -> ProductionScalePlatformContract:
    contracts = tuple(
        item
        for item in (
            installable_live_platform_contract,
            plugin_ecosystem_contract,
            remote_sandbox_policy_contract,
            learning_ops_contract,
            tenant_auth_contract,
        )
        if item is not None
    )
    result = ProductionScalePlatformContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        production_scale_platform_ready=production_scale_platform_ready,
        plugin_ecosystem_available=True,
        plugin_manifest_validation_available=True,
        plugin_permission_policy_available=True,
        plugin_quarantine_available=True,
        remote_sandbox_backend_interface_available=True,
        docker_backend_policy_available=True,
        ssh_backend_policy_available=True,
        network_egress_default_denied=True,
        mount_allowlist_required=True,
        credential_passthrough_default_denied=True,
        eval_registry_available=True,
        error_ledger_available=True,
        promotion_review_available=True,
        candidate_only_learning_available=True,
        tenant_model_available=True,
        principal_model_available=True,
        api_key_auth_contract_available=True,
        role_scope_enforcement_available=True,
        tenant_isolation_contract_available=True,
        persistent_audit_contract_available=True,
        installable_live_platform_contract=installable_live_platform_contract,
        plugin_ecosystem_contract=plugin_ecosystem_contract,
        remote_sandbox_policy_contract=remote_sandbox_policy_contract,
        learning_ops_contract=learning_ops_contract,
        tenant_auth_contract=tenant_auth_contract,
        production_ready=False,
        network_opened=_any_flag(contracts, "network_opened"),
        handler_executed=_any_flag(contracts, "handler_executed"),
        external_delivery_opened=_any_flag(contracts, "external_delivery_opened"),
        credential_material_accessed=_any_flag(contracts, "credential_material_accessed"),
        remote_sandbox_execution_opened=_any_flag(contracts, "remote_sandbox_execution_opened"),
        active_rule_written=_any_flag(contracts, "active_rule_written"),
        authority_widened=_any_flag(contracts, "authority_widened"),
        live_production_claimed=_any_flag(contracts, "live_production_claimed"),
    )
    return result.with_secret_scan()


def _plugin_ecosystem_payload() -> dict[str, JsonValue]:
    return _json_payload(validate_plugin_manifest(_SAFE_PLUGIN_MANIFEST).model_dump(mode="json"))


def _remote_sandbox_policy_payload() -> dict[str, JsonValue]:
    return {
        "decision": "blocked",
        "backend_interface": ["local", "docker", "ssh", "remote"],
        "docker_backend_policy": "default_deny_without_operator_approval",
        "ssh_backend_policy": "default_deny_without_operator_approval",
        "network_egress_policy": "deny_by_default",
        "mount_policy": "allowlist_required",
        "credential_passthrough_policy": "deny_by_default",
        "remote_sandbox_execution_opened": False,
        "network_opened": False,
        "handler_executed": False,
        "credential_material_accessed": False,
    }


def _learning_ops_payload() -> dict[str, JsonValue]:
    return {
        "decision": "report",
        "eval_registry": "available",
        "error_ledger": "candidate_only",
        "promotion_review": "required",
        "automatic_memory_promotion": False,
        "automatic_rule_promotion": False,
        "active_rule_written": False,
        "authority_widened": False,
        "handler_executed": False,
    }


def _tenant_auth_payload() -> dict[str, JsonValue]:
    return {
        "decision": "report",
        "tenant_model": "tenant_id",
        "principal_model": "user_device_subagent_plugin",
        "api_key_auth": "scoped_key_required",
        "role_scope_enforcement": "required",
        "tenant_isolation": "default_deny_cross_tenant",
        "persistent_audit": "append_only_required",
        "credential_material_accessed": False,
        "authority_widened": False,
    }


def _parse_scenario(value: str) -> Optional[ProductionScalePlatformScenario]:
    stripped = value.strip()
    if stripped == "status":
        return "status"
    if stripped == "plugin-ecosystem":
        return "plugin-ecosystem"
    if stripped == "remote-sandbox-policy":
        return "remote-sandbox-policy"
    if stripped == "tenant-auth-contract":
        return "tenant-auth-contract"
    if stripped == "learning-ops":
        return "learning-ops"
    return None


def _any_flag(contracts: tuple[dict[str, JsonValue], ...], key: str) -> bool:
    return any(bool(contract.get(key, False)) for contract in contracts)


def _json_payload(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return json.loads(json.dumps(payload))
