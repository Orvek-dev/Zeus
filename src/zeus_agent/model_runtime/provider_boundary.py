from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeResponse,
)

ProviderBoundaryDecision = Literal["selected", "dry_run", "blocked"]

_MODEL_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class ProviderRawToolCall(BaseModel):
    model_config = _MODEL_CONFIG

    call_id: str
    tool_name: str
    arguments_json: str

    @field_validator("call_id", "tool_name", "arguments_json")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)


class ProviderBoundaryRequest(BaseModel):
    model_config = _MODEL_CONFIG

    provider_kind: str
    provider_id: str
    model_id: str
    messages: tuple[ProviderMessage, ...] = Field(min_length=1)
    tool_calls: tuple[ProviderRawToolCall, ...] = ()
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    live_network: bool = False
    metadata: tuple[ProviderMetadataEntry, ...] = ()

    @field_validator(
        "provider_kind",
        "provider_id",
        "model_id",
        "credential_scope",
        "network_host",
    )
    @classmethod
    def _validate_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class ProviderBoundaryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ProviderBoundaryDecision
    requested_provider_kind: str
    reason: Optional[str] = None
    response: Optional[ProviderRuntimeResponse] = None
    handler_executed: bool = False
    adapter_invoked: bool = False
    client_constructed: bool = False
    network_opened: bool = False
    sdk_imported: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True

    @field_validator("requested_provider_kind", "reason")
    @classmethod
    def _validate_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


__all__ = [
    "ProviderBoundaryDecision",
    "ProviderBoundaryRequest",
    "ProviderBoundaryResult",
    "ProviderRawToolCall",
]
