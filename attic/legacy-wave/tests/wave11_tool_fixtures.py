from __future__ import annotations

from datetime import datetime, timezone

from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.tool_runtime import ToolDefinition, ToolsetDefinition
from zeus_agent.transport_runtime import (
    AuthorityRequirement,
    SandboxProbeDefinition,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
    TransportRegistry,
)

ISSUED_AT = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
EXPIRES_AT = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)


def toolset(*tools: ToolDefinition) -> ToolsetDefinition:
    return ToolsetDefinition(
        toolset_id="wave11.tools",
        display_name="Wave11 Tools",
        tools=tools,
    )


def local_tool(*, input_schema: dict[str, object] | None = None) -> ToolDefinition:
    return ToolDefinition(
        name="local.echo",
        description="Echo local text",
        capability_id="api.tool.echo",
        source="local",
        input_schema=input_schema or {
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
    )


def mcp_tool() -> ToolDefinition:
    return ToolDefinition(
        name="mcp.echo",
        description="Echo MCP text",
        capability_id="mcp.echo",
        source="mcp",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    )


def lease(*capability_ids: str, budget_limit: int = 100) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave11.lease.fixture",
        objective_id="wave11.objective.tool_runtime",
        principal_id="wave11.principal.worker",
        run_id="wave11.run.fixture",
        allowed_capabilities=capability_ids,
        budget_limit=budget_limit,
        evidence_target="mneme.wave11.tool_runtime",
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )


def registry(
    *entries: tuple[str, TransportKind, TransportHealth],
) -> TransportRegistry:
    transport_registry = TransportRegistry()
    for capability_id, kind, health in entries:
        transport_id = "transport.{0}".format(capability_id.replace(".", "_"))
        transport_registry.register(
            TransportAdapterManifest(
                transport_id=transport_id,
                kind=kind,
                display_name="Transport {0}".format(capability_id),
                capability_id=capability_id,
                policy=TransportPolicy(
                    policy_labels=("tool-runtime",),
                    authority_requirements=(
                        AuthorityRequirement(capability_id=capability_id),
                    ),
                ),
                sandbox_probe_ids=("probe.{0}".format(capability_id),),
            ),
        )
        transport_registry.run_probe(
            SandboxProbeDefinition(
                probe_id="probe.{0}".format(capability_id),
                transport_id=transport_id,
                expected_health=health,
            ),
        )
    return transport_registry
