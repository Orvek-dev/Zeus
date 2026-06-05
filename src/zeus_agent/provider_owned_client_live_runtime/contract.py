from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from pydantic import JsonValue

from zeus_agent.provider_owned_client_live_runtime.constants import OBJECTIVE_CONTRACT_ID
from zeus_agent.provider_owned_client_live_runtime.constants import TARGET_VERSION
from zeus_agent.provider_owned_client_live_runtime.models import ProviderOwnedClientLiveContract
from zeus_agent.provider_owned_client_live_runtime.models import ProviderOwnedClientLiveDecision
from zeus_agent.provider_owned_client_live_runtime.models import ProviderOwnedClientLiveScenario


def make_contract(
    *,
    decision: ProviderOwnedClientLiveDecision,
    scenario: ProviderOwnedClientLiveScenario,
    blocked_reasons: tuple[str, ...] = (),
    provider_owned_client_live_ready: bool = False,
    operator_live_opted_in: bool = False,
    endpoint_allowlisted: bool = False,
    secret_material_available: bool = False,
    owned_client_smoke: Optional[dict[str, JsonValue]] = None,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    controlled_external_side_effects: bool = False,
    provider_invoked: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
    material_released: bool = False,
) -> ProviderOwnedClientLiveContract:
    result = ProviderOwnedClientLiveContract(
        decision=decision,
        target_version=TARGET_VERSION,
        release_stage="provider_owned_client_live",
        objective_contract_id=OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        provider_owned_client_live_ready=provider_owned_client_live_ready,
        production_ready=False,
        operator_live_opted_in=operator_live_opted_in,
        endpoint_allowlisted=endpoint_allowlisted,
        secret_material_available=secret_material_available,
        owned_client_smoke=owned_client_smoke,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=controlled_external_side_effects,
        provider_invoked=provider_invoked,
        handler_executed=handler_executed,
        credential_material_accessed=credential_material_accessed,
        material_released=material_released,
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
