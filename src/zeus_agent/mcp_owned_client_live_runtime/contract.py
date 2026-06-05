from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from pydantic import JsonValue

from zeus_agent.mcp_owned_client_live_runtime.constants import OBJECTIVE_CONTRACT_ID
from zeus_agent.mcp_owned_client_live_runtime.constants import TARGET_VERSION
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveContract
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveDecision
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveScenario


def make_contract(
    *,
    decision: McpOwnedClientLiveDecision,
    scenario: McpOwnedClientLiveScenario,
    blocked_reasons: tuple[str, ...] = (),
    mcp_owned_client_live_ready: bool = False,
    operator_live_opted_in: bool = False,
    endpoint_allowlisted: bool = False,
    secret_material_available: bool = False,
    mcp_owned_client_smoke: Optional[dict[str, JsonValue]] = None,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    controlled_external_side_effects: bool = False,
    tool_invoked: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
    material_released: bool = False,
    server_started: bool = False,
    resources_enabled: bool = False,
    prompts_enabled: bool = False,
) -> McpOwnedClientLiveContract:
    result = McpOwnedClientLiveContract(
        decision=decision,
        target_version=TARGET_VERSION,
        release_stage="mcp_owned_client_live",
        objective_contract_id=OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        mcp_owned_client_live_ready=mcp_owned_client_live_ready,
        production_ready=False,
        operator_live_opted_in=operator_live_opted_in,
        endpoint_allowlisted=endpoint_allowlisted,
        secret_material_available=secret_material_available,
        mcp_owned_client_smoke=mcp_owned_client_smoke,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=controlled_external_side_effects,
        tool_invoked=tool_invoked,
        handler_executed=handler_executed,
        credential_material_accessed=credential_material_accessed,
        material_released=material_released,
        server_started=server_started,
        resources_enabled=resources_enabled,
        prompts_enabled=prompts_enabled,
        raw_secret_returned=False,
        external_delivery_opened=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def endpoint_host(endpoint: str) -> Optional[str]:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https":
        return None
    return parsed.hostname


def endpoint_allowlisted(endpoint: str, allowed_hosts: tuple[str, ...]) -> bool:
    host = endpoint_host(endpoint)
    return host is not None and host in allowed_hosts
