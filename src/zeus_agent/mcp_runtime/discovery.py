from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.tool_runtime import ToolDefinition

from .manager_models import McpTransportKind
from .models import JsonObject, object_schema

McpDiscoveryDecision = Literal["allowed", "blocked"]
McpRiskHint = Literal["unknown", "read_only", "destructive"]
McpDiscoveryPayloadValue = Union[str, int, bool, None, list[dict[str, JsonValue]]]
McpDiscoveryPayload = dict[str, McpDiscoveryPayloadValue]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_PROMPT_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "developer message",
    "system prompt",
    "reveal secret",
    "reveal secrets",
    "exfiltrate",
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _validate_id(value: str, field_name: str) -> str:
    normalized = _require_non_empty(value, field_name)
    if _ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError("malformed_{0}".format(field_name))
    return normalized


class McpToolDescriptor(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    capability_id: str
    description: str
    input_schema: JsonObject = Field(default_factory=object_schema)
    output_schema: JsonObject = Field(default_factory=object_schema)
    annotations: JsonObject = Field(default_factory=dict)
    trusted_annotations_applied: bool = False
    risk_hint: McpRiskHint = "unknown"
    authority_granted: bool = False
    prompt_injection_detected: bool = False
    secret_detected: bool = False

    @model_validator(mode="before")
    @classmethod
    def _scan_description(cls, data: JsonValue) -> JsonValue:
        if not isinstance(data, dict):
            return data
        raw_description = data.get("description")
        if not isinstance(raw_description, str):
            return data
        return {
            **data,
            "description": _safe_text(raw_description),
            "prompt_injection_detected": _has_prompt_injection(raw_description),
            "secret_detected": _contains_secret_like(raw_description),
        }

    @field_validator("name", "capability_id")
    @classmethod
    def _validate_ids(cls, value: str, info: ValidationInfo) -> str:
        return _validate_id(value, info.field_name)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("input_schema", "output_schema", "annotations", mode="before")
    @classmethod
    def _redact_json_field(cls, value: JsonValue) -> JsonValue:
        return _redact_json(value)


class McpDiscoverySnapshot(BaseModel):
    model_config = _MODEL_CONFIG

    decision: McpDiscoveryDecision
    reason: str
    server_id: str
    server_label: str
    transport: McpTransportKind
    trusted_server: bool
    tools: tuple[McpToolDescriptor, ...]
    tool_count: int = Field(ge=0)
    next_cursor: Optional[str] = None
    list_changed: bool = False
    unsafe_marker_count: int = Field(default=0, ge=0)
    resources_enabled: bool = False
    prompts_enabled: bool = False
    handler_executed: bool = False
    network_opened: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    @field_validator("server_id", "server_label")
    @classmethod
    def _validate_required_ids(cls, value: str, info: ValidationInfo) -> str:
        return _validate_id(value, info.field_name)

    def to_payload(self) -> McpDiscoveryPayload:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "server_id": self.server_id,
            "server_label": self.server_label,
            "transport": self.transport,
            "trusted_server": self.trusted_server,
            "tool_count": self.tool_count,
            "tools": [tool.model_dump(mode="json") for tool in self.tools],
            "next_cursor": self.next_cursor,
            "list_changed": self.list_changed,
            "unsafe_marker_count": self.unsafe_marker_count,
            "resources_enabled": self.resources_enabled,
            "prompts_enabled": self.prompts_enabled,
            "handler_executed": self.handler_executed,
            "network_opened": self.network_opened,
            "subprocess_started": self.subprocess_started,
            "no_secret_echo": self.no_secret_echo,
            "live_production_claimed": self.live_production_claimed,
        }


def normalize_tools_list_result(
    payload: JsonValue,
    *,
    server_id: str,
    server_label: str,
    transport: McpTransportKind,
    trusted_server: bool = False,
) -> McpDiscoverySnapshot:
    if not isinstance(payload, dict):
        raise ValueError("malformed_mcp_discovery")
    raw_tools = payload.get("tools")
    if not isinstance(raw_tools, list) or not raw_tools:
        raise ValueError("malformed_mcp_discovery")
    tools = tuple(
        _tool_descriptor(
            item,
            server_id=server_id,
            trusted_server=trusted_server,
        )
        for item in raw_tools
    )
    names = [tool.name for tool in tools]
    if len(names) != len(set(names)):
        raise ValueError("duplicate_tool_name")
    snapshot = McpDiscoverySnapshot(
        decision="allowed",
        reason="mcp_tools_list_normalized",
        server_id=server_id,
        server_label=server_label,
        transport=transport,
        trusted_server=trusted_server,
        tools=tools,
        tool_count=len(tools),
        next_cursor=_optional_text(payload.get("nextCursor")),
        list_changed=bool(payload.get("listChanged", False)),
        unsafe_marker_count=sum(1 for tool in tools if tool.prompt_injection_detected or tool.secret_detected),
    )
    return snapshot.model_copy(update={"no_secret_echo": _no_secret_echo(snapshot)})


def tool_entry_from_mcp_tool(
    tool: McpToolDescriptor,
    *,
    server_label: str,
) -> ToolDefinition:
    return ToolDefinition(
        name="{0}.{1}".format(_validate_id(server_label, "server_label"), tool.name),
        description=tool.description,
        capability_id=tool.capability_id,
        source="mcp",
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
    )


def _tool_descriptor(
    value: JsonValue,
    *,
    server_id: str,
    trusted_server: bool,
) -> McpToolDescriptor:
    if not isinstance(value, dict):
        raise ValueError("malformed_mcp_discovery")
    raw_name = value.get("name")
    if not isinstance(raw_name, str):
        raise ValueError("malformed_mcp_discovery")
    name = _validate_id(raw_name, "name")
    annotations = _json_object(value.get("annotations"))
    return McpToolDescriptor(
        name=name,
        capability_id="{0}.{1}".format(_validate_id(server_id, "server_id"), name),
        description=str(value.get("description") or name),
        input_schema=_json_object(value.get("input_schema") or value.get("inputSchema")),
        output_schema=_json_object(value.get("output_schema") or value.get("outputSchema")),
        annotations=annotations,
        trusted_annotations_applied=trusted_server and bool(annotations),
        risk_hint=_risk_hint(annotations, trusted_server=trusted_server),
    )


def _risk_hint(annotations: JsonObject, *, trusted_server: bool) -> McpRiskHint:
    if not trusted_server:
        return "unknown"
    if annotations.get("destructiveHint") is True:
        return "destructive"
    if annotations.get("readOnlyHint") is True:
        return "read_only"
    return "unknown"


def _json_object(value: JsonValue) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _optional_text(value: JsonValue) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("malformed_mcp_discovery")
    return _require_non_empty(value, "next_cursor")


def _redact_json(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_json(item) for key, item in value.items()}
    return value


def _safe_text(value: str) -> str:
    normalized = _require_non_empty(value, "description")
    if _has_prompt_injection(normalized):
        return "[redacted-description]"
    return redact_secret_spans(normalized)


def _has_prompt_injection(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS)


def _contains_secret_like(value: str) -> bool:
    return redact_secret_spans(value) != value


def _no_secret_echo(snapshot: McpDiscoverySnapshot) -> bool:
    serialized = json.dumps(snapshot.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
