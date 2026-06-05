from __future__ import annotations

from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_ALLOWED_HOST
from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_ENDPOINT
from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_QUERY
from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_SECRET_REF
from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_SERVER_ID
from zeus_agent.mcp_owned_client_live_runtime.constants import DEFAULT_TOOL_NAME
from zeus_agent.mcp_owned_client_live_runtime.contract import endpoint_allowlisted
from zeus_agent.mcp_owned_client_live_runtime.contract import make_contract
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveContract
from zeus_agent.mcp_owned_client_live_runtime.pipeline import build_owned_client_smoke_contract

_SUPPORTED_SCENARIOS: frozenset[str] = frozenset(
    {
        "status",
        "blocked-missing-opt-in",
        "blocked-missing-secret",
        "owned-client-smoke",
    }
)


def build_mcp_owned_client_live_contract(
    *,
    scenario: str = "status",
    endpoint: str = DEFAULT_ENDPOINT,
    allowed_host: str = DEFAULT_ALLOWED_HOST,
    secret_ref: str = DEFAULT_SECRET_REF,
    server_id: str = DEFAULT_SERVER_ID,
    tool_name: str = DEFAULT_TOOL_NAME,
    query: str = DEFAULT_QUERY,
) -> McpOwnedClientLiveContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return make_contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_mcp_owned_client_live_scenario",),
        )
    if safe_scenario == "status":
        return make_contract(decision="report", scenario="status")
    if safe_scenario == "blocked-missing-opt-in":
        return _missing_opt_in(endpoint=endpoint, allowed_host=allowed_host)
    if safe_scenario == "blocked-missing-secret":
        return build_owned_client_smoke_contract(
            scenario="blocked-missing-secret",
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            server_id=server_id,
            tool_name=tool_name,
            query=query,
        )
    return build_owned_client_smoke_contract(
        scenario="owned-client-smoke",
        endpoint=endpoint,
        allowed_host=allowed_host,
        secret_ref=secret_ref,
        server_id=server_id,
        tool_name=tool_name,
        query=query,
    )


def _missing_opt_in(*, endpoint: str, allowed_host: str) -> McpOwnedClientLiveContract:
    return make_contract(
        decision="blocked",
        scenario="blocked-missing-opt-in",
        blocked_reasons=("operator_live_opt_in_required",),
        endpoint_allowlisted=endpoint_allowlisted(endpoint, (allowed_host,)),
    )
