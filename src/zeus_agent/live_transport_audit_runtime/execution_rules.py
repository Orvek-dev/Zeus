from __future__ import annotations

from typing import Literal, Optional, Union

from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalTransportResult
from zeus_agent.live_gateway_delivery_adapter_runtime.models import LiveGatewayDeliveryAdapterResult
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportResult
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportResult
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientTransportResult
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalTransportResult
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportResult
from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportResult
from zeus_agent.live_mcp_remote_adapter_runtime.models import LiveMcpRemoteAdapterResult
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportResult
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportResult
from zeus_agent.live_provider_direct_adapter_runtime.models import LiveProviderDirectAdapterResult
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientTransportResult
from zeus_agent.live_provider_http_transport_runtime import LiveProviderHttpTransportResult
from zeus_agent.live_provider_loopback_transport_runtime import LiveProviderLoopbackTransportResult

LiveTransportAdapterKind = Literal["provider", "gateway", "mcp"]
LiveTransportExecutionResult = Union[
    LiveProviderLoopbackTransportResult,
    LiveProviderDirectAdapterResult,
    LiveProviderOwnedClientTransportResult,
    LiveProviderExternalTransportResult,
    LiveProviderHttpTransportResult,
    LiveGatewayDeliveryAdapterResult,
    LiveGatewayExternalTransportResult,
    LiveGatewayOwnedClientTransportResult,
    LiveGatewayHttpTransportResult,
    LiveGatewayLoopbackTransportResult,
    LiveMcpExternalTransportResult,
    LiveMcpRemoteAdapterResult,
    LiveMcpOwnedClientTransportResult,
    LiveMcpHttpTransportResult,
    LiveMcpLoopbackTransportResult,
]

_CONTROLLED_EXTERNAL_TYPES = (
    LiveProviderExternalTransportResult,
    LiveProviderDirectAdapterResult,
    LiveProviderOwnedClientTransportResult,
    LiveGatewayExternalTransportResult,
    LiveGatewayDeliveryAdapterResult,
    LiveGatewayOwnedClientTransportResult,
    LiveMcpExternalTransportResult,
    LiveMcpRemoteAdapterResult,
    LiveMcpOwnedClientTransportResult,
)
_LOOPBACK_HTTP_TYPES = (LiveProviderHttpTransportResult, LiveGatewayHttpTransportResult, LiveMcpHttpTransportResult)
_CLEANUP_RECEIPTS = {
    "provider": "provider-loopback-no-network",
    "gateway": "gateway-loopback-no-delivery",
    "mcp": "mcp-loopback-no-remote-server",
}
_HTTP_CLEANUP_RECEIPTS = {
    "provider": "provider-local-http-client-closed",
    "provider_external": "provider-external-http-client-closed",
    "gateway": "gateway-local-http-client-closed",
    "gateway_external": "gateway-external-http-client-closed",
    "mcp": "mcp-local-http-client-closed",
}


def execution_adapter_kind(execution: LiveTransportExecutionResult) -> LiveTransportAdapterKind:
    if isinstance(
        execution,
        (
            LiveProviderLoopbackTransportResult,
            LiveProviderHttpTransportResult,
            LiveProviderExternalTransportResult,
            LiveProviderDirectAdapterResult,
            LiveProviderOwnedClientTransportResult,
        ),
    ):
        return "provider"
    if isinstance(
        execution,
        (
            LiveGatewayLoopbackTransportResult,
            LiveGatewayHttpTransportResult,
            LiveGatewayExternalTransportResult,
            LiveGatewayDeliveryAdapterResult,
            LiveGatewayOwnedClientTransportResult,
        ),
    ):
        return "gateway"
    return "mcp"


def execution_reasons(*, adapter_kind: LiveTransportAdapterKind, execution: LiveTransportExecutionResult) -> tuple[str, ...]:
    reasons = []
    if execution.decision != "executed":
        reasons.append("execution_not_executed")
    if not execution.live_transport_enabled:
        reasons.append("execution_live_transport_not_seen")
    if not execution.handler_executed or not execution.execution_allowed:
        reasons.append("execution_handler_not_confirmed")
    if isinstance(execution, _CONTROLLED_EXTERNAL_TYPES):
        reasons.extend(_controlled_external_reasons(adapter_kind=adapter_kind, execution=execution))
        return tuple(dict.fromkeys(reasons))
    if not execution.transport_activation_bound or not execution.adapter_plan_bound:
        reasons.append("execution_not_bound")
    if adapter_kind == "provider" and not execution.provider_envelope_bound:
        reasons.append("provider_execution_not_bound")
    if isinstance(execution, LiveProviderDirectAdapterResult) and not execution.production_claim_bound:
        reasons.append("provider_production_claim_not_bound")
    if adapter_kind == "gateway" and not execution.gateway_envelope_bound:
        reasons.append("gateway_execution_not_bound")
    if isinstance(execution, LiveGatewayDeliveryAdapterResult) and not execution.production_claim_bound:
        reasons.append("gateway_production_claim_not_bound")
    if adapter_kind == "mcp" and not execution.mcp_envelope_bound:
        reasons.append("mcp_execution_not_bound")
    if isinstance(execution, LiveMcpRemoteAdapterResult) and not execution.production_claim_bound:
        reasons.append("mcp_production_claim_not_bound")
    return tuple(dict.fromkeys(reasons))


def side_effect_reasons(*, adapter_kind: LiveTransportAdapterKind, execution: LiveTransportExecutionResult) -> tuple[str, ...]:
    reasons = []
    if execution.network_opened and not _allowed_network_execution(execution):
        reasons.append("{0}_network_opened".format(adapter_kind))
    if execution.external_delivery_opened and not _allowed_external_delivery_execution(execution):
        reasons.append("{0}_external_delivery_opened".format(adapter_kind))
    if execution.credential_material_accessed:
        reasons.append("{0}_credential_material_accessed".format(adapter_kind))
    if execution.raw_secret_returned:
        reasons.append("{0}_raw_secret_returned".format(adapter_kind))
    if not execution.no_secret_echo:
        reasons.append("{0}_secret_echo_detected".format(adapter_kind))
    if execution.live_production_claimed:
        reasons.append("{0}_live_production_claimed".format(adapter_kind))
    if adapter_kind == "mcp":
        reasons.extend(_mcp_side_effect_reasons(execution))
    return tuple(dict.fromkeys(reasons))


def cleanup_verified(*, adapter_kind: LiveTransportAdapterKind, cleanup_receipt: Optional[str]) -> bool:
    if adapter_kind == "provider" and cleanup_receipt in (_HTTP_CLEANUP_RECEIPTS["provider"], _HTTP_CLEANUP_RECEIPTS["provider_external"]):
        return True
    if adapter_kind == "provider" and cleanup_receipt == "provider-owned-client-closed":
        return True
    if adapter_kind == "provider" and cleanup_receipt == "provider-direct-client-closed":
        return True
    if adapter_kind == "gateway" and cleanup_receipt in (_HTTP_CLEANUP_RECEIPTS["gateway"], _HTTP_CLEANUP_RECEIPTS["gateway_external"]):
        return True
    if adapter_kind == "gateway" and cleanup_receipt == "gateway-owned-client-closed":
        return True
    if adapter_kind == "gateway" and cleanup_receipt == "gateway-delivery-adapter-client-closed":
        return True
    if adapter_kind == "mcp" and cleanup_receipt == _HTTP_CLEANUP_RECEIPTS["mcp"]:
        return True
    if adapter_kind == "mcp" and cleanup_receipt == "mcp-remote-server-client-closed":
        return True
    if adapter_kind == "mcp" and cleanup_receipt == "mcp-remote-adapter-client-closed":
        return True
    if adapter_kind == "mcp" and cleanup_receipt == "mcp-owned-client-closed":
        return True
    return cleanup_receipt == _CLEANUP_RECEIPTS[adapter_kind]


def controlled_external_side_effects(execution: LiveTransportExecutionResult) -> bool:
    return isinstance(execution, _CONTROLLED_EXTERNAL_TYPES) and execution.controlled_external_side_effects


def _controlled_external_reasons(*, adapter_kind: LiveTransportAdapterKind, execution: LiveTransportExecutionResult) -> tuple[str, ...]:
    reasons = []
    if not execution.policy_bound or not execution.preflight_bound:
        reasons.append("execution_not_bound")
    if not execution.remote_executor_preflight_bound or not execution.remote_target_bound:
        reasons.append("execution_not_bound")
    if adapter_kind == "provider" and not execution.provider_envelope_bound:
        reasons.append("provider_execution_not_bound")
    if isinstance(execution, LiveProviderDirectAdapterResult) and not execution.production_claim_bound:
        reasons.append("provider_production_claim_not_bound")
    if adapter_kind == "gateway" and not execution.gateway_envelope_bound:
        reasons.append("gateway_execution_not_bound")
    if isinstance(execution, LiveGatewayDeliveryAdapterResult) and not execution.production_claim_bound:
        reasons.append("gateway_production_claim_not_bound")
    if adapter_kind == "mcp" and not execution.mcp_envelope_bound:
        reasons.append("mcp_execution_not_bound")
    if isinstance(execution, LiveMcpRemoteAdapterResult) and not execution.production_claim_bound:
        reasons.append("mcp_production_claim_not_bound")
    return tuple(dict.fromkeys(reasons))


def _allowed_network_execution(execution: LiveTransportExecutionResult) -> bool:
    if isinstance(execution, _CONTROLLED_EXTERNAL_TYPES):
        return execution.controlled_external_side_effects and execution.non_loopback_network_opened and execution.remote_executor_preflight_bound
    if isinstance(execution, _LOOPBACK_HTTP_TYPES):
        return execution.local_http_loopback and not execution.non_loopback_network_opened
    return False


def _allowed_external_delivery_execution(execution: LiveTransportExecutionResult) -> bool:
    return isinstance(
        execution,
        (
            LiveGatewayExternalTransportResult,
            LiveGatewayDeliveryAdapterResult,
            LiveGatewayOwnedClientTransportResult,
        ),
    ) and execution.controlled_external_side_effects


def _mcp_side_effect_reasons(execution: LiveTransportExecutionResult) -> tuple[str, ...]:
    reasons = []
    if execution.server_started:
        reasons.append("mcp_remote_server_started")
    if execution.resources_enabled:
        reasons.append("mcp_resources_enabled")
    if execution.prompts_enabled:
        reasons.append("mcp_prompts_enabled")
    return tuple(reasons)
