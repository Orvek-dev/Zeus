from __future__ import annotations

from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.real_product_platform_runtime.models import RealProductPlatformContract
from zeus_agent.real_product_platform_runtime.models import RealProductPlatformDecision
from zeus_agent.real_product_platform_runtime.models import RealProductPlatformScenario

_TARGET_VERSION: Final = "v1.7.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.7.0.product_ux_platform_status"


def build_contract(
    *,
    decision: RealProductPlatformDecision,
    scenario: RealProductPlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    persona_contract: Optional[dict[str, JsonValue]] = None,
    platform_contract: Optional[dict[str, JsonValue]] = None,
    live_cockpit_contract: Optional[dict[str, JsonValue]] = None,
    model_cockpit_contract: Optional[dict[str, JsonValue]] = None,
    mcp_cockpit_contract: Optional[dict[str, JsonValue]] = None,
    runtime_cockpit_contract: Optional[dict[str, JsonValue]] = None,
    status_surface_count: int = 0,
    blocked_surface_count: int = 0,
    operator_commands: tuple[str, ...] = (),
    product_platform_ready: bool = False,
    persona_surface_ready: bool = False,
    platform_status_ready: bool = False,
    live_status_ready: bool = False,
    operator_command_map_ready: bool = False,
    public_boundary_ready: bool = False,
    raw_secret_marker_detected: bool = False,
    cleanup_performed: bool = False,
) -> RealProductPlatformContract:
    child_contracts = (
        persona_contract,
        platform_contract,
        live_cockpit_contract,
        model_cockpit_contract,
        mcp_cockpit_contract,
        runtime_cockpit_contract,
    )
    network_opened = _any_flag(child_contracts, "network_opened")
    handler_executed = _any_flag(child_contracts, "handler_executed")
    credential_material_accessed = _any_flag(child_contracts, "credential_material_accessed")
    external_delivery_opened = _any_flag(child_contracts, "external_delivery_opened")
    live_production_claimed = _any_flag(child_contracts, "live_production_claimed")
    safe_ready = (
        product_platform_ready
        and not network_opened
        and not handler_executed
        and not credential_material_accessed
        and not external_delivery_opened
        and not live_production_claimed
    )
    return RealProductPlatformContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="product_ux_platform_status",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        product_platform_ready=safe_ready,
        persona_surface_ready=persona_surface_ready,
        platform_status_ready=platform_status_ready,
        live_status_ready=live_status_ready,
        operator_command_map_ready=operator_command_map_ready,
        public_boundary_ready=public_boundary_ready,
        production_ready=False,
        persona_contract=persona_contract,
        platform_contract=platform_contract,
        live_cockpit_contract=live_cockpit_contract,
        model_cockpit_contract=model_cockpit_contract,
        mcp_cockpit_contract=mcp_cockpit_contract,
        runtime_cockpit_contract=runtime_cockpit_contract,
        status_surface_count=status_surface_count,
        blocked_surface_count=blocked_surface_count,
        operator_command_count=len(operator_commands),
        operator_commands=operator_commands,
        chat_turn_started=_any_flag(child_contracts, "chat_turn_started"),
        api_server_started=_any_flag(child_contracts, "api_server_started"),
        gateway_daemon_started=_any_flag(child_contracts, "gateway_daemon_started"),
        credential_material_accessed=credential_material_accessed,
        network_opened=network_opened,
        external_delivery_opened=external_delivery_opened,
        handler_executed=handler_executed,
        authority_widened=_any_flag(child_contracts, "authority_widened"),
        active_rule_written=_any_flag(child_contracts, "active_rule_written"),
        raw_secret_marker_detected=raw_secret_marker_detected,
        raw_secret_returned=False,
        live_production_claimed=live_production_claimed,
        cleanup_performed=cleanup_performed,
    ).with_secret_scan()


def _any_flag(contracts: tuple[Optional[dict[str, JsonValue]], ...], key: str) -> bool:
    return any(contract is not None and bool(contract.get(key, False)) for contract in contracts)
