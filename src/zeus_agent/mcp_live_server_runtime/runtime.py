from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_mcp_activation_policy_runtime import LiveMcpActivationPolicyRuntime
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.mcp_live_server_runtime.support import build_activation
from zeus_agent.mcp_live_server_runtime.support import build_adapter_plan
from zeus_agent.mcp_live_server_runtime.support import build_transport_lease
from zeus_agent.mcp_live_server_runtime.support import safe_surface_scan
from zeus_agent.mcp_live_server_runtime.support import unsafe_surface_scan
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer

McpLiveServerDecision = Literal["report", "blocked"]
McpLiveServerScenario = Literal["status", "loopback-smoke", "prompt-injection-scan"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v1.0.0-rc.3"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.3.mcp_live_server"
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)
class McpLiveServerContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: McpLiveServerDecision
    target_version: str
    release_stage: Literal["mcp_live_server"]
    objective_contract_id: str
    scenario: McpLiveServerScenario
    blocked_reasons: tuple[str, ...] = ()
    mcp_live_server_contract_available: bool = True
    mcp_catalog_available: bool = True
    mcp_activation_policy_available: bool = True
    mcp_request_envelope_available: bool = True
    mcp_loopback_http_available: bool = True
    mcp_credentialed_http_available: bool = True
    mcp_remote_server_available: bool = False
    mcp_resources_enabled: bool = False
    mcp_prompts_enabled: bool = False
    mcp_live_server_ready: bool = False
    production_ready: bool = False
    mcp_smoke: Optional[dict[str, JsonValue]] = None
    mcp_surface_scan: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> McpLiveServerContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        return self.model_copy(update={"no_secret_echo": not any(marker in serialized for marker in _SECRET_MARKERS)})


def build_mcp_live_server_contract(
    *,
    scenario: str = "status",
    secret_ref: str = "env://ZEUS_RC3_MCP_TOKEN",
    query: str = "Zeus MCP live server checkpoint",
) -> McpLiveServerContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in {"status", "loopback-smoke", "prompt-injection-scan"}:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_mcp_live_server_scenario",),
        )
    if safe_scenario == "status":
        return _contract(decision="report", scenario="status", mcp_surface_scan=safe_surface_scan())
    if safe_scenario == "prompt-injection-scan":
        scan = unsafe_surface_scan()
        return _contract(
            decision="blocked",
            scenario="prompt-injection-scan",
            blocked_reasons=("mcp_prompt_injection_detected",),
            mcp_surface_scan=scan,
        )
    return _loopback_smoke(secret_ref=secret_ref, query=query)


def _loopback_smoke(*, secret_ref: str, query: str) -> McpLiveServerContract:
    transport_lease = build_transport_lease(network_host="127.0.0.1")
    secret_material = LiveSecretMaterialRuntime().check(
        transport_lease=transport_lease,
        secret_ref=secret_ref,
        allow_material_access=True,
    )
    if secret_material.decision != "available":
        return _contract(
            decision="blocked",
            scenario="loopback-smoke",
            blocked_reasons=secret_material.blocked_reasons,
            mcp_smoke={
                "transport_lease": transport_lease.to_payload(),
                "secret_material": secret_material.to_payload(),
            },
            credential_material_accessed=secret_material.credential_material_accessed,
        )

    server = Wave16ProviderHttpServer()
    server.start()
    try:
        endpoint = "{0}/v1/chat/completions".format(server.base_url)
        envelope = LiveMcpRequestRuntime().prepare(
            transport_lease=transport_lease,
            secret_material=secret_material,
            server_id="mcp.github",
            tool_name="repo.search",
            endpoint=endpoint,
            arguments={"query": query},
        )
        adapter_plan = build_adapter_plan(envelope)
        activation_policy = LiveMcpActivationPolicyRuntime().plan(
            server_id="mcp.github",
            startup_requested=True,
            resources_requested=False,
            prompts_requested=False,
            approval_ref="approval://rc3/mcp.github/startup",
        )
        activation = build_activation(adapter_plan)
        execution = LiveMcpHttpTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            mcp_envelope=envelope,
            transport_kind="local_http",
            execution_ref="mcp-live-server://rc3/loopback",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="mcp",
            execution=execution,
            audit_ref="live-audit://rc3/mcp-live-server",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=execution.redacted_response or {},
            response_ref="live-response://rc3/mcp-live-server",
        )
    finally:
        server.shutdown()

    ready = (
        execution.decision == "executed"
        and audit.decision == "audit_ready"
        and redaction.decision == "redacted"
        and activation_policy.decision == "activation_planned"
        and server.shutdown_complete
        and execution.non_loopback_network_opened is False
        and execution.live_production_claimed is False
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="loopback-smoke",
        blocked_reasons=() if ready else tuple(execution.blocked_reasons or audit.blocked_reasons),
        mcp_smoke={
            "activation_policy": activation_policy.to_payload(),
            "transport_lease": transport_lease.to_payload(),
            "secret_material": secret_material.to_payload(),
            "mcp_envelope": envelope.to_payload(),
            "adapter_plan": adapter_plan.to_payload(),
            "activation": activation.to_payload(),
            "execution": execution.to_payload(),
            "audit": audit.to_payload(),
            "redaction": redaction.to_payload(),
            "server_request_count": server.request_count("/v1/chat/completions"),
            "server_shutdown_complete": server.shutdown_complete,
        },
        mcp_surface_scan=safe_surface_scan(),
        mcp_live_server_ready=ready,
        network_opened=execution.network_opened,
        non_loopback_network_opened=execution.non_loopback_network_opened,
        handler_executed=execution.handler_executed,
        credential_material_accessed=secret_material.credential_material_accessed,
    )


def _contract(
    *,
    decision: McpLiveServerDecision,
    scenario: McpLiveServerScenario,
    blocked_reasons: tuple[str, ...] = (),
    mcp_smoke: Optional[dict[str, JsonValue]] = None,
    mcp_surface_scan: Optional[dict[str, JsonValue]] = None,
    mcp_live_server_ready: bool = False,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
) -> McpLiveServerContract:
    result = McpLiveServerContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="mcp_live_server",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        mcp_smoke=mcp_smoke,
        mcp_surface_scan=mcp_surface_scan,
        mcp_live_server_ready=mcp_live_server_ready,
        production_ready=False,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        handler_executed=handler_executed,
        credential_material_accessed=credential_material_accessed,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()
