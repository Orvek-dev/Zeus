from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.installable_live_platform_runtime.models import InstallableLivePlatformContract
from zeus_agent.installable_live_platform_runtime.models import InstallableLivePlatformDecision
from zeus_agent.installable_live_platform_runtime.models import InstallableLivePlatformScenario
from zeus_agent.live_readiness_runtime import LiveReadinessRuntime
from zeus_agent.plugin_runtime import validate_plugin_manifest
from zeus_agent.production_safe_live_platform_runtime import build_production_safe_live_platform_contract
from zeus_agent.real_execution_runtime import build_real_execution_contract
from zeus_agent.security.credentials import contains_secret_material

_SAFE_PLUGIN_MANIFEST: Final[dict[str, JsonValue]] = {
    "plugin_id": "zeus.installable_local",
    "name": "Installable Local Plugin",
    "version": "0.1.0",
    "entrypoint": "plugins/installable_local.py",
    "permissions": ["tool.read", "wiki.read"],
    "dependencies": ["pydantic"],
    "sha256": "a" * 64,
}


def build_installable_live_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    operator_note: Optional[str] = None,
) -> InstallableLivePlatformContract:
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
            blocked_reasons=("unsupported_installable_live_platform_scenario",),
        )
    if parsed == "plugin-manifest":
        return _plugin_manifest_contract()
    if parsed == "remote-sandbox-policy":
        return _remote_sandbox_policy_contract(home=home)
    return _status_contract(home=home)


def _status_contract(*, home: Optional[Path]) -> InstallableLivePlatformContract:
    readiness = _json_payload(LiveReadinessRuntime().build_report().to_payload())
    production_safe = _json_payload(build_production_safe_live_platform_contract(
        scenario="status",
        home=home,
    ).to_payload())
    plugin = _json_payload(validate_plugin_manifest(_SAFE_PLUGIN_MANIFEST).model_dump(mode="json"))
    ready = (
        readiness["decision"] == "report"
        and production_safe["decision"] == "report"
        and plugin["decision"] == "quarantined"
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="status",
        blocked_reasons=() if ready else ("installable_live_surface_unavailable",),
        installable_live_platform_ready=ready,
        live_readiness_contract=readiness,
        production_safe_contract=production_safe,
        plugin_manifest_contract=plugin,
    )


def _plugin_manifest_contract() -> InstallableLivePlatformContract:
    plugin = _json_payload(validate_plugin_manifest(_SAFE_PLUGIN_MANIFEST).model_dump(mode="json"))
    return _contract(
        decision="report",
        scenario="plugin-manifest",
        installable_live_platform_ready=False,
        plugin_manifest_contract=plugin,
    )


def _remote_sandbox_policy_contract(*, home: Optional[Path]) -> InstallableLivePlatformContract:
    remote = _json_payload(build_real_execution_contract(scenario="blocked-remote", home=home).to_payload())
    return _contract(
        decision="blocked",
        scenario="remote-sandbox-policy",
        blocked_reasons=("remote_sandbox_blocked",),
        installable_live_platform_ready=False,
        remote_sandbox_policy_contract=remote,
    )


def _contract(
    *,
    decision: InstallableLivePlatformDecision,
    scenario: InstallableLivePlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    installable_live_platform_ready: bool = False,
    live_readiness_contract: Optional[dict[str, JsonValue]] = None,
    production_safe_contract: Optional[dict[str, JsonValue]] = None,
    plugin_manifest_contract: Optional[dict[str, JsonValue]] = None,
    remote_sandbox_policy_contract: Optional[dict[str, JsonValue]] = None,
) -> InstallableLivePlatformContract:
    contracts = tuple(
        value
        for value in (
            live_readiness_contract,
            production_safe_contract,
            plugin_manifest_contract,
            remote_sandbox_policy_contract,
        )
        if value is not None
    )
    result = InstallableLivePlatformContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        installable_live_platform_ready=installable_live_platform_ready,
        provider_install_surface_available=True,
        mcp_install_surface_available=True,
        gateway_install_surface_available=True,
        api_install_surface_available=True,
        cli_install_surface_available=True,
        python_library_install_surface_available=True,
        plugin_manifest_install_surface_available=True,
        local_sandbox_policy_install_surface_available=True,
        remote_sandbox_policy_install_surface_available=True,
        live_readiness_contract=live_readiness_contract,
        production_safe_contract=production_safe_contract,
        plugin_manifest_contract=plugin_manifest_contract,
        remote_sandbox_policy_contract=remote_sandbox_policy_contract,
        production_ready=False,
        network_opened=_any_flag(contracts, "network_opened"),
        handler_executed=_any_flag(contracts, "handler_executed"),
        external_delivery_opened=_any_flag(contracts, "external_delivery_opened"),
        credential_material_accessed=_any_flag(contracts, "credential_material_accessed"),
        remote_sandbox_execution_opened=_any_flag(contracts, "remote_execution_opened"),
        active_rule_written=_any_flag(contracts, "active_rule_written"),
        authority_widened=_any_flag(contracts, "authority_widened"),
        live_production_claimed=_any_flag(contracts, "live_production_claimed"),
    )
    return result.with_secret_scan()


def _parse_scenario(value: str) -> Optional[InstallableLivePlatformScenario]:
    stripped = value.strip()
    if stripped == "status":
        return "status"
    if stripped == "plugin-manifest":
        return "plugin-manifest"
    if stripped == "remote-sandbox-policy":
        return "remote-sandbox-policy"
    return None


def _any_flag(contracts: tuple[dict[str, JsonValue], ...], key: str) -> bool:
    return any(bool(contract.get(key, False)) for contract in contracts)


def _json_payload(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return json.loads(json.dumps(payload))
