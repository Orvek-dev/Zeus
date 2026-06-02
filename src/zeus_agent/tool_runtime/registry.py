from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional

from pydantic import JsonValue, ValidationError

from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityGraph, CapabilityRisk
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.runtime_lease.builder import RuntimeIntakeRequest, RuntimeLeaseBuilder
from zeus_agent.security.credentials import redact_secret_like
from zeus_agent.transport_runtime import TransportExecutionGate, TransportExecutionGateRequest, TransportKind, TransportRegistry

from .models import (
    JsonObject, McpDiscoveryInspectionResult, ToolDefinition, ToolExecutionRequest,
    ToolExecutionResult, ToolHandler, ToolsetDefinition,
    UntrustedMcpDiscovery, UntrustedToolCall,
)

_PROMPT_INJECTION_MARKERS = ("ignore previous", "ignore all previous", "system prompt", "developer message", "reveal secret", "exfiltrate")
_RUNTIME_KINDS = {"local": "api_tool", "mcp": "mcp"}
_TRANSPORT_KINDS = {"local": TransportKind.api, "mcp": TransportKind.mcp}


@dataclass(frozen=True)
class _ToolRecord:
    toolset_id: str
    tool: ToolDefinition


class ToolRuntimeRegistry:
    def __init__(
        self,
        *,
        transport_registry: Optional[TransportRegistry] = None,
        transport_gate: Optional[TransportExecutionGate] = None,
        lease_builder: Optional[RuntimeLeaseBuilder] = None,
    ) -> None:
        self._toolsets: dict[str, ToolsetDefinition] = {}
        self._tools: dict[str, _ToolRecord] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._enabled: set[str] = set()
        self._lease_builder = lease_builder or RuntimeLeaseBuilder()
        self._transport_gate = transport_gate
        if self._transport_gate is None and transport_registry is not None:
            self._transport_gate = TransportExecutionGate(transport_registry)

    def register_toolset(
        self,
        toolset: ToolsetDefinition,
        *,
        handlers: Optional[Mapping[str, ToolHandler]] = None,
    ) -> None:
        if toolset.toolset_id in self._toolsets:
            raise ValueError("duplicate_toolset_id")
        handler_map = dict(handlers or {})
        known_names = {tool.name for tool in toolset.tools}
        if not set(handler_map).issubset(known_names):
            raise ValueError("unknown_tool_handler")
        for tool in toolset.tools:
            if tool.name in self._tools:
                raise ValueError("duplicate_tool_name")
        self._toolsets[toolset.toolset_id] = toolset
        for tool in toolset.tools:
            self._tools[tool.name] = _ToolRecord(toolset.toolset_id, tool)
        self._handlers.update(handler_map)
        if toolset.enabled:
            self._enabled.add(toolset.toolset_id)

    def enable(self, toolset_id: str) -> None:
        self._require_toolset(toolset_id)
        self._enabled.add(toolset_id)

    def disable(self, toolset_id: str) -> None:
        self._require_toolset(toolset_id)
        self._enabled.discard(toolset_id)

    def compile_model_schema(
        self,
        lease: Optional[RuntimeLease],
        *,
        now: Optional[datetime] = None,
    ) -> list[JsonObject]:
        schemas: list[JsonObject] = []
        for record in self._enabled_records():
            auth = self._authorize(record.tool, None, lease, now=now)
            if auth.decision != "allowed" or auth.authority is None:
                continue
            graph = CapabilityGraph([_descriptor(record.tool)])
            schemas.extend(
                redacted
                for entry in graph.compile_model_schema(profile="coding-agent", authority=auth.authority)
                for redacted in (_as_optional_json_object(_redact_json(entry, schema_text=True)),)
                if redacted is not None
            )
        return schemas

    def execute(
        self,
        request: ToolExecutionRequest,
        lease: Optional[RuntimeLease],
        *,
        now: Optional[datetime] = None,
    ) -> ToolExecutionResult:
        record = self._tools.get(request.tool_name)
        if record is None:
            return _blocked("unknown_tool", tool_name=request.tool_name)
        if record.toolset_id not in self._enabled:
            return _blocked("disabled_toolset", record=record)

        auth = self._authorize(record.tool, request, lease, now=now)
        if auth.decision != "allowed" or auth.authority is None:
            return _blocked(auth.reason, record=record, redacted_input=auth.redacted_input)

        transport = self._evaluate_transport(record.tool, auth.authority)
        if transport is not None:
            return _blocked(transport.reason, record=record, redacted_input=transport.redacted_input)

        handler = self._handlers.get(record.tool.name)
        called = {"value": False}

        def wrapped(payload: JsonObject) -> JsonValue:
            called["value"] = True
            if handler is None:
                return None
            return handler(payload)

        broker = CapabilityBroker(
            graph=CapabilityGraph([_descriptor(record.tool)]),
            handlers={} if handler is None else {record.tool.capability_id: wrapped},
        )
        broker_response = broker.dispatch(capability_id=record.tool.capability_id, payload=request.arguments, context=auth.authority)
        return _from_broker(record, broker_response, handler_executed=called["value"])

    def inspect_mcp_discovery(self, untrusted: JsonValue) -> McpDiscoveryInspectionResult:
        try:
            discovery = UntrustedMcpDiscovery.model_validate(untrusted)
            toolset = ToolsetDefinition(
                toolset_id=discovery.toolset_id or "mcp.{0}".format(discovery.server_id),
                display_name=discovery.display_name or "MCP {0}".format(discovery.server_id),
                tools=tuple(_mcp_tool(tool) for tool in discovery.tools),
            )
        except (ValidationError, ValueError):
            return McpDiscoveryInspectionResult(decision="blocked", reason="malformed_mcp_discovery")
        return McpDiscoveryInspectionResult(decision="allowed", reason="mcp_discovery_allowed", toolset=toolset)

    def inspect_untrusted_call(
        self,
        untrusted: JsonValue,
        lease: Optional[RuntimeLease],
        *,
        now: Optional[datetime] = None,
    ) -> ToolExecutionResult:
        try:
            call = UntrustedToolCall.model_validate(untrusted)
        except ValidationError:
            return _blocked("malformed_tool_json")
        request = ToolExecutionRequest(tool_name=call.tool_name, arguments=call.arguments, tool_call_id=call.tool_call_id, budget_required=call.budget_required)
        return self.execute(request, lease, now=now)

    def _authorize(
        self,
        tool: ToolDefinition,
        request: Optional[ToolExecutionRequest],
        lease: Optional[RuntimeLease],
        *,
        now: Optional[datetime],
    ):
        budget = tool.budget_required if request is None or request.budget_required is None else request.budget_required
        evidence_target = lease.evidence_target if isinstance(lease, RuntimeLease) else "mneme.wave11.tool_runtime"
        intake = RuntimeIntakeRequest(
            runtime_kind=_RUNTIME_KINDS[tool.source],
            capability_id=tool.capability_id,
            credential_scope=tool.credential_scope,
            network_host=tool.network_host,
            budget_required=budget,
            evidence_target=evidence_target,
        )
        return self._lease_builder.authorize(lease, intake, now=now)

    def _evaluate_transport(self, tool: ToolDefinition, authority):
        if self._transport_gate is None:
            return None
        request = TransportExecutionGateRequest(capability_id=tool.capability_id, transport_kind=_TRANSPORT_KINDS[tool.source], credential_scope=tool.credential_scope)
        result = self._transport_gate.evaluate(request, authority)
        if result.decision == "blocked":
            return result
        return None

    def _enabled_records(self) -> tuple[_ToolRecord, ...]:
        return tuple(record for record in self._tools.values() if record.toolset_id in self._enabled)

    def _require_toolset(self, toolset_id: str) -> None:
        if toolset_id not in self._toolsets:
            raise ValueError("unknown_toolset")


def _descriptor(tool: ToolDefinition) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=tool.capability_id,
        name=tool.name,
        risk=CapabilityRisk.low,
        input_schema=_as_optional_json_object(_redact_json(tool.input_schema, schema_text=True)) or {},
        output_schema=_as_optional_json_object(_redact_json(tool.output_schema, schema_text=False)) or {},
        description=_redact_schema_text(tool.description),
    )


def _mcp_tool(tool) -> ToolDefinition:
    return ToolDefinition(
        name=tool.name,
        description=_redact_schema_text(tool.description),
        capability_id=tool.capability_id or "mcp.{0}".format(tool.name),
        source="mcp",
        input_schema=_as_optional_json_object(_redact_json(tool.input_schema, schema_text=True)) or {},
        output_schema=_as_optional_json_object(_redact_json(tool.output_schema, schema_text=False)) or {},
        budget_required=tool.budget_required,
    )


def _blocked(
    reason: str,
    *,
    record: Optional[_ToolRecord] = None,
    tool_name: Optional[str] = None,
    redacted_input: Optional[str] = None,
) -> ToolExecutionResult:
    tool = None if record is None else record.tool
    return ToolExecutionResult(
        decision="blocked", reason=redact_secret_like(reason),
        tool_name=tool_name if tool is None else tool.name,
        toolset_id=None if record is None else record.toolset_id,
        capability_id=None if tool is None else tool.capability_id,
        handler_executed=False, network_opened=False, redacted_input=redacted_input,
    )


def _from_broker(
    record: _ToolRecord,
    response: dict,
    *,
    handler_executed: bool,
) -> ToolExecutionResult:
    reason = response.get("reason")
    evidence = response.get("evidence")
    result = response.get("result")
    decision = response.get("decision")
    if decision not in {"allowed", "blocked", "error"}:
        decision = "error"
        reason = "malformed_broker_response"
    return ToolExecutionResult(
        decision=decision, reason=redact_secret_like(reason) if isinstance(reason, str) else None,
        tool_name=record.tool.name, toolset_id=record.toolset_id,
        capability_id=record.tool.capability_id, result=_redact_json(result, schema_text=False),
        evidence=_as_optional_json_object(_redact_json(evidence, schema_text=False)),
        handler_executed=handler_executed, network_opened=False,
    )


def _redact_json(value, *, schema_text: bool) -> JsonValue:
    if isinstance(value, str):
        return _redact_schema_text(value) if schema_text else redact_secret_like(value)
    if isinstance(value, list):
        return [_redact_json(item, schema_text=schema_text) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redact_json(item, schema_text=schema_text)
            for key, item in value.items()
        }
    return value


def _redact_schema_text(value: str) -> str:
    secret_redacted = redact_secret_like(value)
    if secret_redacted != value:
        return secret_redacted
    lowered = value.lower()
    if any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS):
        return "[redacted-description]"
    return value


def _as_optional_json_object(value: JsonValue) -> Optional[JsonObject]:
    if isinstance(value, dict):
        return value
    return None
