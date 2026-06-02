from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field

from zeus_agent.agent_runtime.compression import ContextCompressionPolicy
from zeus_agent.agent_runtime.lineage import (
    ConversationLineageEvent,
    ConversationLineageStore,
)
from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderRuntimeRequest,
    ProviderToolDefinition,
)
from zeus_agent.model_runtime.provider_registry import (
    EVIDENCE_TARGET as PROVIDER_EVIDENCE_TARGET,
    ProviderRegistry,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.tool_runtime import (
    ToolDefinition,
    ToolExecutionRequest,
    ToolRuntimeRegistry,
    ToolsetDefinition,
)
from zeus_agent.transport_runtime import (
    AuthorityRequirement,
    SandboxProbeDefinition,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
    TransportRegistry,
)
from zeus_agent.verification_runtime.engine import (
    VerificationEngine,
    VerificationObligation,
)
from zeus_agent.workloop_runtime import OrchestrationLane, build_work_loop_plan

_ISSUED_AT: Final = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
_TOOL_EVIDENCE_TARGET: Final = "mneme.wave12.conversation_runtime"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=1, ge=0)

    def allows(self, attempts: int) -> bool:
        return attempts <= self.max_attempts


class Wave12ConversationRuntime:
    def __init__(self, home: Path) -> None:
        self._home = home
        self._compression = ContextCompressionPolicy()

    def run_turn(self, message: str) -> dict[str, object]:
        normalized = message.strip()
        if normalized == "":
            return _blocked_turn("empty_message")

        compression = self._compression.evaluate((normalized,))
        if compression.decision == "blocked":
            return _blocked_turn(compression.reason)

        provider_lease = wave12_provider_lease()
        tool_lease = wave12_runtime_lease()
        tool_runtime = wave12_tool_runtime()
        schema = tool_runtime.compile_model_schema(tool_lease, now=_ISSUED_AT)
        provider = ProviderRegistry().generate(
            _provider_request(normalized, schema),
            provider_lease,
            now=_ISSUED_AT,
        )
        tool_request = _planned_tool_call(normalized)
        tool_result = tool_runtime.execute(tool_request, tool_lease, now=_ISSUED_AT)
        lineage_recorded = ConversationLineageStore(self._home).record(
            ConversationLineageEvent(
                session_id="wave12.session.fixture",
                turn_id="wave12.turn.001",
                provider_response_id=provider.response_id,
                tool_call_id=tool_request.tool_call_id or "wave12.call.echo",
                tool_name=tool_request.tool_name,
                tool_decision=tool_result.decision,
                evidence_recorded=tool_result.evidence is not None,
            ),
        )
        verification = _verification_allowed(tool_result.evidence is not None)
        serialized = json.dumps(
            {
                "provider": provider.model_dump(mode="json"),
                "tool_result": tool_result.model_dump(mode="json"),
            },
            sort_keys=True,
        )
        return {
            "scenario_id": "C001",
            "conversation_runtime_created": True,
            "provider_invoked": provider.decision == "selected",
            "tool_schema_compiled": bool(schema),
            "tool_call_planned": tool_request.tool_name == "local.echo",
            "broker_dispatch_allowed": tool_result.decision == "allowed",
            "tool_result_recorded": tool_result.evidence is not None,
            "session_lineage_recorded": lineage_recorded,
            "context_compressed": compression.compressed,
            "verification_completion_allowed": verification,
            "handler_executed": tool_result.handler_executed,
            "network_opened": provider.network_opened or tool_result.network_opened,
            "no_secret_echo": "ghp_" not in serialized and "sk-" not in serialized,
        }


def wave12_runtime_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave12.lease.conversation",
        objective_id="wave12.objective.conversation",
        principal_id="wave12.principal.agent",
        run_id="wave12.run.conversation",
        allowed_capabilities=("provider.fake.generate", "api.tool.echo"),
        budget_limit=100,
        evidence_target=_TOOL_EVIDENCE_TARGET,
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )


def wave12_provider_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave12.lease.provider",
        objective_id="wave12.objective.conversation",
        principal_id="wave12.principal.agent",
        run_id="wave12.run.provider",
        allowed_capabilities=("provider.fake.generate",),
        budget_limit=100,
        evidence_target=PROVIDER_EVIDENCE_TARGET,
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )


def wave12_tool_runtime() -> ToolRuntimeRegistry:
    runtime = ToolRuntimeRegistry(transport_registry=_transport_registry())
    runtime.register_toolset(
        ToolsetDefinition(
            toolset_id="wave12.tools",
            display_name="Wave12 Tools",
            tools=(
                ToolDefinition(
                    name="local.echo",
                    description="Echo Wave12 evidence text",
                    capability_id="api.tool.echo",
                    input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                ),
            ),
        ),
        handlers={"local.echo": lambda payload: {"echo": payload["text"], "source": "wave12"}},
    )
    return runtime


def wave12_retry_limit_enforced() -> bool:
    return not RetryPolicy(max_attempts=1).allows(2)


def wave12_completion_gate_blocks_missing_evidence() -> bool:
    return not _verification_allowed(False)


def wave12_blocked_message(reason: str) -> dict[str, object]:
    return _blocked_turn(reason)


def _provider_request(
    message: str,
    schema: list[dict[str, object]],
) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind="fake",
        provider_id="fake.provider",
        model_id="fake.wave12",
        messages=(ProviderMessage(role="user", content=message),),
        tools=tuple(_provider_tool(entry) for entry in schema),
    )


def _provider_tool(entry: dict[str, object]) -> ProviderToolDefinition:
    function = entry.get("function")
    name = "local.echo"
    description = "Wave12 echo tool"
    if isinstance(function, dict):
        if isinstance(function.get("name"), str):
            name = function["name"]
        if isinstance(function.get("description"), str):
            description = function["description"]
    return ProviderToolDefinition(
        name=name,
        description=description,
        input_schema={"type": "object"},
    )


def _planned_tool_call(message: str) -> ToolExecutionRequest:
    return ToolExecutionRequest(
        tool_name="local.echo",
        arguments={"text": message},
        tool_call_id="wave12.call.echo",
    )


def _transport_registry() -> TransportRegistry:
    registry = TransportRegistry()
    registry.register(
        TransportAdapterManifest(
            transport_id="wave12.transport.api_tool_echo",
            kind=TransportKind.api,
            display_name="Wave12 API Tool Echo",
            capability_id="api.tool.echo",
            policy=TransportPolicy(
                policy_labels=("wave12",),
                authority_requirements=(AuthorityRequirement(capability_id="api.tool.echo"),),
            ),
            sandbox_probe_ids=("wave12.probe.api_tool_echo",),
        ),
    )
    registry.run_probe(
        SandboxProbeDefinition(
            probe_id="wave12.probe.api_tool_echo",
            transport_id="wave12.transport.api_tool_echo",
            expected_health=TransportHealth.healthy,
        ),
    )
    return registry


def _verification_allowed(evidence_present: bool) -> bool:
    target: Optional[str] = "main-orchestrator-script-pty" if evidence_present else None
    plan = build_work_loop_plan(
        goal_contract_id="wave12.conversation",
        normalized_goal="Run a governed Wave12 conversation turn.",
        deliverables=("conversation-runtime",),
        acceptance_criteria=("REQ-ZEUS-WAVE12-001:S1",),
        lanes=(
            OrchestrationLane(
                lane_id="wave12-runtime",
                owned_paths=("src/zeus_agent/agent_runtime/",),
                stop_condition="tool result and lineage recorded",
                manual_qa_channel="cli_stdout",
                evidence_target=target,
            ),
        ),
        verification_obligations_count=1,
    )
    summary = VerificationEngine().evaluate(
        plan,
        (
            VerificationObligation(
                obligation_id="wave12-obligation-runtime",
                requirement_id="REQ-ZEUS-WAVE12-001:S1",
                lane_id="wave12-runtime",
                obligation_type="runtime",
                evidence_target=target,
                evidence_status="passed" if evidence_present else "missing",
            ),
        ),
    )
    return summary.completion_allowed


def _blocked_turn(reason: str) -> dict[str, object]:
    return {
        "decision": "blocked",
        "reason": reason,
        "handler_executed": False,
        "network_opened": False,
    }
