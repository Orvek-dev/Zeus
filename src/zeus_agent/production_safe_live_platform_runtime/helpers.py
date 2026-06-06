from __future__ import annotations

from typing import Optional

from pydantic import JsonValue

from zeus_agent.production_safe_live_platform_runtime.models import ProductionSafeLivePlatformScenario
from zeus_agent.production_safe_live_platform_runtime.models import SECRET_MARKERS


def boundary_reasons(
    *,
    gateway: dict[str, JsonValue],
    browser: dict[str, JsonValue],
    remote: dict[str, JsonValue],
) -> tuple[str, ...]:
    reasons = []
    if "external_delivery_blocked" in gateway["blocked_reasons"]:
        reasons.append("external_gateway_delivery_blocked")
    if "live_navigation_not_supported" in browser["blocked_reasons"]:
        reasons.append("browser_live_navigation_blocked")
    if "remote_execution_not_supported" in remote["blocked_reasons"]:
        reasons.append("remote_sandbox_blocked")
    return tuple(reasons)


def report(*contracts: dict[str, JsonValue]) -> bool:
    return all(contract["decision"] == "report" for contract in contracts)


def no_side_effects(*contracts: dict[str, JsonValue]) -> bool:
    return not any(
        any_flag(contracts, key)
        for key in (
            "network_opened",
            "external_delivery_opened",
            "credential_material_accessed",
            "live_production_claimed",
        )
    )


def compact_contracts(*values: Optional[dict[str, JsonValue]]) -> tuple[dict[str, JsonValue], ...]:
    return tuple(value for value in values if value is not None)


def any_flag(contracts: tuple[dict[str, JsonValue], ...], key: str) -> bool:
    return any(bool(contract.get(key, False)) for contract in contracts)


def parse_scenario(value: str) -> ProductionSafeLivePlatformScenario:
    if value == "status":
        return "status"
    if value == "provider-mcp-smoke":
        return "provider-mcp-smoke"
    if value == "platform-execution-boundary":
        return "platform-execution-boundary"
    return "activation-required-block"


def has_secret_marker(value: Optional[str]) -> bool:
    if value is None:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)
