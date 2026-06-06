from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import JsonValue

from zeus_agent.production_safe_live_platform_runtime.helpers import any_flag
from zeus_agent.production_safe_live_platform_runtime.helpers import boundary_reasons
from zeus_agent.production_safe_live_platform_runtime.helpers import compact_contracts
from zeus_agent.production_safe_live_platform_runtime.helpers import has_secret_marker
from zeus_agent.production_safe_live_platform_runtime.helpers import no_side_effects
from zeus_agent.production_safe_live_platform_runtime.helpers import parse_scenario
from zeus_agent.production_safe_live_platform_runtime.helpers import report
from zeus_agent.production_safe_live_platform_runtime.models import ProductionSafeLivePlatformContract
from zeus_agent.production_safe_live_platform_runtime.models import ProductionSafeLivePlatformDecision
from zeus_agent.production_safe_live_platform_runtime.models import ProductionSafeLivePlatformScenario
from zeus_agent.real_execution_runtime import build_real_execution_contract
from zeus_agent.real_mcp_runtime import build_real_mcp_contract
from zeus_agent.real_platform_runtime import build_real_platform_contract
from zeus_agent.real_provider_runtime import build_real_provider_contract
from zeus_agent.zeus_identity_activation_runtime import build_zeus_identity_activation_contract

_SUPPORTED_SCENARIOS = frozenset(
    {
        "status",
        "provider-mcp-smoke",
        "platform-execution-boundary",
        "activation-required-block",
    },
)


def build_production_safe_live_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    operator_note: Optional[str] = None,
) -> ProductionSafeLivePlatformContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_production_safe_live_platform_scenario",),
        )
    parsed = parse_scenario(safe_scenario)
    if has_secret_marker(operator_note):
        return _contract(
            decision="blocked",
            scenario=parsed,
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    if parsed == "activation-required-block":
        return _activation_required_block()
    if parsed == "provider-mcp-smoke":
        return _provider_mcp_smoke()
    if parsed == "platform-execution-boundary":
        return _platform_execution_boundary(home=home)
    return _status(home=home)


def _status(*, home: Optional[Path]) -> ProductionSafeLivePlatformContract:
    activation = _activation_ready()
    provider = build_real_provider_contract(scenario="status").to_payload()
    mcp = build_real_mcp_contract(scenario="status").to_payload()
    platform = build_real_platform_contract(scenario="api-dry-run", home=home).to_payload()
    execution = build_real_execution_contract(scenario="status", home=home).to_payload()
    ready = report(activation, provider, mcp, platform, execution) and no_side_effects(
        activation,
        provider,
        mcp,
        platform,
        execution,
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="status",
        blocked_reasons=() if ready else ("production_safe_connection_surface_unavailable",),
        activation_contract=activation,
        provider_contract=provider,
        mcp_contract=mcp,
        platform_contract=platform,
        execution_contract=execution,
        production_safe_connections_ready=ready,
        provider_connection_ready=provider["decision"] == "report",
        mcp_connection_ready=mcp["decision"] == "report",
        platform_connection_ready=platform["decision"] == "report",
    )


def _provider_mcp_smoke() -> ProductionSafeLivePlatformContract:
    activation = _activation_ready()
    provider = build_real_provider_contract(scenario="status").to_payload()
    mcp = build_real_mcp_contract(scenario="setup-dry-run").to_payload()
    ready = report(activation, provider, mcp) and no_side_effects(activation, provider, mcp)
    return _contract(
        decision="report" if ready else "blocked",
        scenario="provider-mcp-smoke",
        blocked_reasons=() if ready else ("provider_mcp_connection_unavailable",),
        activation_contract=activation,
        provider_contract=provider,
        mcp_contract=mcp,
        production_safe_connections_ready=ready,
        provider_connection_ready=provider["decision"] == "report",
        mcp_connection_ready=mcp["decision"] == "report",
    )


def _platform_execution_boundary(*, home: Optional[Path]) -> ProductionSafeLivePlatformContract:
    activation = _activation_ready()
    gateway = build_real_platform_contract(scenario="gateway-blocked-external", home=home).to_payload()
    browser = build_real_execution_contract(scenario="browser-blocked-live", home=home).to_payload()
    remote = build_real_execution_contract(scenario="blocked-remote", home=home).to_payload()
    reasons = boundary_reasons(gateway=gateway, browser=browser, remote=remote)
    ready = len(reasons) == 3 and no_side_effects(activation, gateway, browser, remote)
    return _contract(
        decision="blocked",
        scenario="platform-execution-boundary",
        blocked_reasons=reasons,
        activation_contract=activation,
        gateway_boundary_contract=gateway,
        browser_boundary_contract=browser,
        remote_sandbox_boundary_contract=remote,
        platform_boundary_ready=ready,
        execution_boundary_ready=ready,
        blocked_surface_count=len(reasons),
        production_safe_connections_ready=False,
    )


def _activation_required_block() -> ProductionSafeLivePlatformContract:
    activation = build_zeus_identity_activation_contract(
        scenario="activation-check",
        objective_id="objective.v190",
        approval_id="approval.v190",
        credential_binding_ref="credential.v190",
        sandbox_policy_ref="sandbox.v190",
        audit_receipt_ref="audit.v190",
    ).to_payload()
    return _contract(
        decision="blocked",
        scenario="activation-required-block",
        blocked_reasons=tuple(str(reason) for reason in activation["blocked_reasons"]),
        activation_contract=activation,
        production_safe_connections_ready=False,
    )


def _contract(
    *,
    decision: ProductionSafeLivePlatformDecision,
    scenario: ProductionSafeLivePlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    blocked_surface_count: int = 0,
    production_safe_connections_ready: bool = False,
    provider_connection_ready: bool = False,
    mcp_connection_ready: bool = False,
    platform_connection_ready: bool = False,
    platform_boundary_ready: bool = False,
    execution_boundary_ready: bool = False,
    raw_secret_marker_detected: bool = False,
    activation_contract: Optional[dict[str, JsonValue]] = None,
    provider_contract: Optional[dict[str, JsonValue]] = None,
    mcp_contract: Optional[dict[str, JsonValue]] = None,
    platform_contract: Optional[dict[str, JsonValue]] = None,
    execution_contract: Optional[dict[str, JsonValue]] = None,
    gateway_boundary_contract: Optional[dict[str, JsonValue]] = None,
    browser_boundary_contract: Optional[dict[str, JsonValue]] = None,
    remote_sandbox_boundary_contract: Optional[dict[str, JsonValue]] = None,
) -> ProductionSafeLivePlatformContract:
    contracts = compact_contracts(
        activation_contract,
        provider_contract,
        mcp_contract,
        platform_contract,
        execution_contract,
        gateway_boundary_contract,
        browser_boundary_contract,
        remote_sandbox_boundary_contract,
    )
    result = ProductionSafeLivePlatformContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        blocked_surface_count=blocked_surface_count,
        production_safe_connections_ready=production_safe_connections_ready,
        provider_connection_ready=provider_connection_ready,
        mcp_connection_ready=mcp_connection_ready,
        platform_connection_ready=platform_connection_ready,
        platform_boundary_ready=platform_boundary_ready,
        execution_boundary_ready=execution_boundary_ready,
        raw_secret_marker_detected=raw_secret_marker_detected,
        activation_contract=activation_contract,
        provider_contract=provider_contract,
        mcp_contract=mcp_contract,
        platform_contract=platform_contract,
        execution_contract=execution_contract,
        gateway_boundary_contract=gateway_boundary_contract,
        browser_boundary_contract=browser_boundary_contract,
        remote_sandbox_boundary_contract=remote_sandbox_boundary_contract,
        api_server_started=any_flag(contracts, "server_started"),
        gateway_daemon_started=any_flag(contracts, "gateway_daemon_started"),
        browser_navigation_opened=any_flag(contracts, "browser_navigation_opened"),
        remote_sandbox_opened=any_flag(contracts, "remote_execution_opened"),
        credential_material_accessed=any_flag(contracts, "credential_material_accessed"),
        network_opened=any_flag(contracts, "network_opened"),
        external_delivery_opened=any_flag(contracts, "external_delivery_opened"),
        handler_executed=any_flag(contracts, "handler_executed"),
        authority_widened=any_flag(contracts, "authority_widened"),
        active_rule_written=any_flag(contracts, "active_rule_written"),
        live_production_claimed=any_flag(contracts, "live_production_claimed"),
    )
    return result.with_secret_scan()


def _activation_ready() -> dict[str, JsonValue]:
    return build_zeus_identity_activation_contract(
        scenario="activation-check",
        objective_id="objective.v190",
        lease_id="lease.v190",
        approval_id="approval.v190",
        credential_binding_ref="credential.v190",
        sandbox_policy_ref="sandbox.v190",
        audit_receipt_ref="audit.v190",
    ).to_payload()

