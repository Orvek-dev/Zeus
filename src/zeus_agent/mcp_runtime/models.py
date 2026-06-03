from __future__ import annotations

import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import redact_secret_spans

JsonObject = dict[str, JsonValue]
McpDecision = Literal["planned", "blocked"]
McpQuarantineState = Literal["clear", "quarantined"]
McpTrustLevel = Literal["low", "medium", "high"]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)
_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_PROMPT_INJECTION_MARKERS: Final = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "developer message",
    "system prompt",
    "reveal secret",
    "reveal secrets",
    "exfiltrate",
)


def object_schema() -> JsonObject:
    return {"type": "object", "properties": {}}


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


def _contains_secret_like(value: str) -> bool:
    normalized = value.strip()
    return redact_secret_spans(normalized) != normalized


def _has_prompt_injection(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS)


def _safe_description(value: str) -> str:
    normalized = _require_non_empty(value, "description")
    if _has_prompt_injection(normalized):
        return "[redacted-description]"
    return redact_secret_spans(normalized)


def _redact_json(value: JsonValue, *, schema_text: bool) -> JsonValue:
    if isinstance(value, str):
        return _safe_description(value) if schema_text else redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_json(item, schema_text=schema_text) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redact_json(item, schema_text=schema_text)
            for key, item in value.items()
        }
    return value


def _coerce_tuple(value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
    if isinstance(value, list):
        return tuple(value)
    return value


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return tuple(seen)


class McpToolManifest(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    capability_id: str
    description: str
    input_schema: JsonObject = Field(default_factory=object_schema)
    output_schema: JsonObject = Field(default_factory=object_schema)
    description_prompt_injection_detected: bool = False
    description_secret_detected: bool = False

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
            "description": _safe_description(raw_description),
            "description_prompt_injection_detected": _has_prompt_injection(
                raw_description,
            ),
            "description_secret_detected": _contains_secret_like(raw_description),
        }

    @field_validator("name", "capability_id")
    @classmethod
    def _validate_scoped_id(cls, value: str, info: ValidationInfo) -> str:
        return _validate_id(value, info.field_name)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return _safe_description(value)

    @field_validator("input_schema", "output_schema", mode="before")
    @classmethod
    def _redact_schema(cls, value: JsonValue) -> JsonValue:
        return _redact_json(value, schema_text=True)


class McpServerManifest(BaseModel):
    model_config = _MODEL_CONFIG

    server_id: str
    display_name: str
    source_ref: Optional[str] = None
    source_pinned: bool = True
    trust_level: McpTrustLevel = "medium"
    description: str
    tools: tuple[McpToolManifest, ...] = Field(min_length=1)
    description_prompt_injection_detected: bool = False
    description_secret_detected: bool = False
    quarantine_state: McpQuarantineState = "clear"
    quarantine_reasons: tuple[str, ...] = ()

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
            "description": _safe_description(raw_description),
            "description_prompt_injection_detected": _has_prompt_injection(
                raw_description,
            ),
            "description_secret_detected": _contains_secret_like(raw_description),
        }

    @field_validator("server_id")
    @classmethod
    def _validate_server_id(cls, value: str) -> str:
        return _validate_id(value, "server_id")

    @field_validator("display_name", "description", "source_ref")
    @classmethod
    def _validate_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        if info.field_name == "description":
            return _safe_description(value)
        return redact_secret_spans(_require_non_empty(value, info.field_name))

    @field_validator("tools", mode="before")
    @classmethod
    def _coerce_tools(cls, value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
        return _coerce_tuple(value)

    @field_validator("quarantine_reasons", mode="before")
    @classmethod
    def _coerce_reasons(cls, value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
        return _coerce_tuple(value)

    @field_validator("quarantine_reasons")
    @classmethod
    def _validate_quarantine_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            redact_secret_spans(_require_non_empty(value, "quarantine_reasons"))
            for value in values
        )

    @model_validator(mode="after")
    def _derive_quarantine(self) -> "McpServerManifest":
        reasons: list[str] = []
        if not self.source_pinned:
            reasons.append("mcp_manifest_unpinned")
        if self.source_ref is None:
            reasons.append("mcp_manifest_ref_missing")
        if self.description_prompt_injection_detected:
            reasons.append("mcp_server_prompt_injection")
        if self.description_secret_detected:
            reasons.append("mcp_server_secret_like_description")
        for tool in self.tools:
            if tool.description_prompt_injection_detected:
                reasons.append("mcp_tool_prompt_injection:{0}".format(tool.name))
            if tool.description_secret_detected:
                reasons.append("mcp_tool_secret_like_description:{0}".format(tool.name))
        quarantine_reasons = _unique((*self.quarantine_reasons, *tuple(reasons)))
        quarantine_state: McpQuarantineState = "quarantined" if quarantine_reasons else "clear"
        object.__setattr__(self, "quarantine_state", quarantine_state)
        object.__setattr__(self, "quarantine_reasons", quarantine_reasons)
        return self


class McpDispatchEnvelope(BaseModel):
    model_config = _MODEL_CONFIG

    server_id: str
    source_ref: Optional[str]
    tool_names: tuple[str, ...]
    capability_ids: tuple[str, ...]
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False


class McpEvidenceEnvelope(BaseModel):
    model_config = _MODEL_CONFIG

    surface_kind: Literal["mcp"] = "mcp"
    server_id: str
    source_ref: Optional[str]
    source_pinned: bool
    trust_level: McpTrustLevel
    tool_count: int = Field(ge=0)
    quarantine_state: McpQuarantineState
    quarantine_reasons: tuple[str, ...]
    prompt_injection_detected: bool
    secret_detected: bool
    no_secret_echo: bool = True


class McpFacadeEnvelope(BaseModel):
    model_config = _MODEL_CONFIG

    decision: McpDecision
    reason: str
    dispatch: McpDispatchEnvelope
    evidence: McpEvidenceEnvelope
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True


__all__ = [
    "JsonObject",
    "McpDecision",
    "McpDispatchEnvelope",
    "McpEvidenceEnvelope",
    "McpFacadeEnvelope",
    "McpQuarantineState",
    "McpServerManifest",
    "McpToolManifest",
    "McpTrustLevel",
]
