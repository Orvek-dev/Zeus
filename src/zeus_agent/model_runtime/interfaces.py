from __future__ import annotations

import json
from typing import Final, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationInfo,
    field_validator,
)

ProviderRuntimeKind = Literal[
    "fake",
    "local_llm",
    "openai_compatible",
    "anthropic_metadata",
]
ProviderRuntimeDecision = Literal["selected", "dry_run", "blocked"]
ProviderJsonScalar = Union[str, int, float, bool, None]
ProviderJsonValue = Union[ProviderJsonScalar, list[str], dict[str, str]]
ProviderMetadataValue = ProviderJsonScalar
ProviderSchemaValue = Union[ProviderJsonScalar, list[str], dict[str, str]]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)
_ARGUMENTS_ADAPTER: Final[TypeAdapter[dict[str, ProviderJsonValue]]] = TypeAdapter(
    dict[str, ProviderJsonValue],
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _metadata_value(
    entries: tuple[ProviderMetadataEntry, ...],
    key: str,
) -> Optional[ProviderMetadataValue]:
    normalized = _require_non_empty(key, "metadata_key")
    for entry in entries:
        if entry.key == normalized:
            return entry.value
    return None


class ProviderMetadataEntry(BaseModel):
    model_config = _MODEL_CONFIG

    key: str
    value: ProviderMetadataValue
    is_authority: bool = False

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        return _require_non_empty(value, "key")


class ProviderMessage(BaseModel):
    model_config = _MODEL_CONFIG

    role: str
    content: str

    @field_validator("role", "content")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)


class ProviderToolDefinition(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    description: str
    input_schema: dict[str, ProviderSchemaValue]
    strict: bool = True

    @field_validator("name", "description")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)


class ProviderToolCall(BaseModel):
    model_config = _MODEL_CONFIG

    call_id: str
    tool_name: str
    arguments_json: str

    @field_validator("call_id", "tool_name")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("arguments_json")
    @classmethod
    def _validate_arguments_json(cls, value: str) -> str:
        normalized = _require_non_empty(value, "arguments_json")
        try:
            decoded = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise ValueError("arguments_json must be a JSON object string") from exc
        if not isinstance(decoded, dict):
            raise ValueError("arguments_json must be a JSON object string")
        return normalized

    def arguments_as_dict(self) -> dict[str, ProviderJsonValue]:
        return _ARGUMENTS_ADAPTER.validate_json(self.arguments_json)


class ProviderToolResult(BaseModel):
    model_config = _MODEL_CONFIG

    call_id: str
    output: str
    is_error: bool = False

    @field_validator("call_id")
    @classmethod
    def _validate_call_id(cls, value: str) -> str:
        return _require_non_empty(value, "call_id")


class ProviderUsage(BaseModel):
    model_config = _MODEL_CONFIG

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    budget_units: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


class ProviderRuntimeRequest(BaseModel):
    model_config = _MODEL_CONFIG

    provider_kind: ProviderRuntimeKind
    provider_id: str
    model_id: str
    messages: tuple[ProviderMessage, ...] = Field(min_length=1)
    tools: tuple[ProviderToolDefinition, ...] = ()
    tool_choice: str = "auto"
    parallel_tool_calls: bool = True
    max_output_tokens: Optional[int] = Field(default=None, gt=0)
    stream: bool = False
    response_format: Optional[str] = None
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    live_network: bool = False
    metadata: tuple[ProviderMetadataEntry, ...] = ()

    @field_validator(
        "provider_id",
        "model_id",
        "tool_choice",
        "response_format",
        "credential_scope",
        "network_host",
    )
    @classmethod
    def _validate_optional_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    def metadata_value(self, key: str) -> Optional[ProviderMetadataValue]:
        return _metadata_value(self.metadata, key)


class ProviderRuntimeResponse(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ProviderRuntimeDecision
    provider_kind: ProviderRuntimeKind
    provider_id: str
    model_id: str
    response_id: str
    content: str
    tool_calls: tuple[ProviderToolCall, ...] = ()
    tool_results: tuple[ProviderToolResult, ...] = ()
    stop_reason: Optional[str] = None
    usage: ProviderUsage
    fallback_route: Optional[str] = None
    metadata: tuple[ProviderMetadataEntry, ...] = ()
    reason: Optional[str] = None
    handler_executed: bool = False
    network_opened: bool = False
    sdk_imported: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True

    @field_validator(
        "provider_id",
        "model_id",
        "response_id",
        "stop_reason",
        "fallback_route",
        "reason",
    )
    @classmethod
    def _validate_optional_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    def metadata_value(self, key: str) -> Optional[ProviderMetadataValue]:
        return _metadata_value(self.metadata, key)


__all__ = [
    "ProviderJsonScalar",
    "ProviderJsonValue",
    "ProviderMessage",
    "ProviderMetadataEntry",
    "ProviderMetadataValue",
    "ProviderRuntimeDecision",
    "ProviderRuntimeKind",
    "ProviderRuntimeRequest",
    "ProviderRuntimeResponse",
    "ProviderSchemaValue",
    "ProviderToolCall",
    "ProviderToolDefinition",
    "ProviderToolResult",
    "ProviderUsage",
]
