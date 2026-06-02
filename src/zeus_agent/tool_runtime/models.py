from __future__ import annotations

import json
import re
from typing import Callable, Final, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator, model_validator

JsonObject = dict[str, JsonValue]
ToolSource = Literal["local", "mcp"]
ToolDecision = Literal["allowed", "blocked", "error"]
ToolHandler = Callable[[JsonObject], JsonValue]

_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_STRICT_ALIAS_MODEL: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    populate_by_name=True,
    strict=True,
)


def object_schema() -> JsonObject:
    return {"type": "object", "properties": {}}


def _validate_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if _ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError("malformed_{0}".format(field_name))
    return normalized


def _tuple_boundary(value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
    if isinstance(value, list):
        return tuple(value)
    return value


class ToolDefinition(BaseModel):
    model_config = _STRICT_MODEL

    name: str
    description: str
    capability_id: str
    source: ToolSource = "local"
    input_schema: JsonObject = Field(default_factory=object_schema)
    output_schema: JsonObject = Field(default_factory=object_schema)
    budget_required: int = Field(default=1, ge=0)
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None

    @field_validator("name", "capability_id")
    @classmethod
    def _validate_scoped_text(cls, value: str, info: ValidationInfo) -> str:
        return _validate_id(value, info.field_name)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must be non-empty")
        return normalized

    @field_validator("credential_scope", "network_host")
    @classmethod
    def _validate_optional_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("{0} must be non-empty".format(info.field_name))
        return normalized

    @model_validator(mode="after")
    def _validate_capability_namespace(self) -> "ToolDefinition":
        prefix = capability_prefix(self.source)
        if not self.capability_id.startswith(prefix):
            raise ValueError("runtime_kind_capability_mismatch")
        return self


class ToolsetDefinition(BaseModel):
    model_config = _STRICT_MODEL

    toolset_id: str
    display_name: str
    tools: tuple[ToolDefinition, ...]
    enabled: bool = True

    @field_validator("tools", mode="before")
    @classmethod
    def _coerce_tools_tuple(cls, value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
        return _tuple_boundary(value)

    @field_validator("toolset_id")
    @classmethod
    def _validate_toolset_id(cls, value: str) -> str:
        return _validate_id(value, "toolset_id")

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must be non-empty")
        return normalized

    @model_validator(mode="after")
    def _validate_unique_tools(self) -> "ToolsetDefinition":
        names = [tool.name for tool in self.tools]
        if not names:
            raise ValueError("tools must be non-empty")
        if len(names) != len(set(names)):
            raise ValueError("duplicate_tool_name")
        return self


class ToolExecutionRequest(BaseModel):
    model_config = _STRICT_MODEL

    tool_name: str
    arguments: JsonObject = Field(default_factory=dict)
    tool_call_id: Optional[str] = None
    budget_required: Optional[int] = Field(default=None, ge=0)

    @field_validator("tool_name")
    @classmethod
    def _validate_tool_name(cls, value: str) -> str:
        return _validate_id(value, "tool_name")

    @field_validator("tool_call_id")
    @classmethod
    def _validate_tool_call_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_id(value, "tool_call_id")


class ToolExecutionResult(BaseModel):
    model_config = _STRICT_MODEL

    decision: ToolDecision
    reason: Optional[str] = None
    tool_name: Optional[str] = None
    toolset_id: Optional[str] = None
    capability_id: Optional[str] = None
    result: Optional[JsonValue] = None
    evidence: Optional[JsonObject] = None
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True
    redacted_input: Optional[str] = None


class McpDiscoveryTool(BaseModel):
    model_config = _STRICT_ALIAS_MODEL

    name: str
    description: str
    input_schema: JsonObject = Field(
        default_factory=object_schema,
        validation_alias=AliasChoices("input_schema", "inputSchema"),
    )
    output_schema: JsonObject = Field(default_factory=object_schema)
    capability_id: Optional[str] = None
    budget_required: int = Field(default=1, ge=0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _validate_id(value, "name")

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_id(value, "capability_id")


class UntrustedMcpDiscovery(BaseModel):
    model_config = _STRICT_MODEL

    server_id: str
    tools: tuple[McpDiscoveryTool, ...]
    toolset_id: Optional[str] = None
    display_name: Optional[str] = None

    @field_validator("tools", mode="before")
    @classmethod
    def _coerce_tools_tuple(cls, value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
        return _tuple_boundary(value)

    @field_validator("server_id", "toolset_id")
    @classmethod
    def _validate_optional_ids(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return _validate_id(value, info.field_name)


class McpDiscoveryInspectionResult(BaseModel):
    model_config = _STRICT_MODEL

    decision: Literal["allowed", "blocked"]
    reason: str
    toolset: Optional[ToolsetDefinition] = None
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True


class UntrustedToolCall(BaseModel):
    model_config = _STRICT_MODEL

    tool_name: str
    arguments: JsonObject = Field(default_factory=dict)
    tool_call_id: Optional[str] = None
    budget_required: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalize_call_shape(cls, value: JsonValue) -> JsonValue:
        if not isinstance(value, dict):
            raise ValueError("malformed_tool_json")
        data = dict(value)
        function = data.pop("function", None)
        if isinstance(function, dict):
            data.setdefault("tool_name", function.get("name"))
            data.setdefault("arguments", function.get("arguments", {}))
        if "name" in data and "tool_name" not in data:
            data["tool_name"] = data.pop("name")
        if "id" in data and "tool_call_id" not in data:
            data["tool_call_id"] = data.pop("id")
        data["arguments"] = _parse_arguments(data.get("arguments", {}))
        return data

    @field_validator("tool_name")
    @classmethod
    def _validate_tool_name(cls, value: str) -> str:
        return _validate_id(value, "tool_name")


def capability_prefix(source: ToolSource) -> str:
    if source == "local":
        return "api.tool."
    if source == "mcp":
        return "mcp."
    raise AssertionError("unreachable tool source: {0}".format(source))


def _parse_arguments(value: JsonValue) -> JsonObject:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("malformed_tool_json") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("malformed_tool_json")
