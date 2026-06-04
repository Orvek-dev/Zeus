from __future__ import annotations

from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from .models import JsonObject, McpServerManifest, McpToolManifest

McpTransportKind = Literal["stdio", "http"]
McpRuntimeDecision = Literal["allowed", "blocked"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)


class McpDiscoveryClient(Protocol):
    def start(self) -> None: ...

    def list_tools(self) -> JsonValue: ...

    def stop(self) -> None: ...

    def metadata(self) -> JsonObject: ...


class McpRuntimeServerSpec(BaseModel):
    model_config = _MODEL_CONFIG

    server_id: str
    transport: McpTransportKind
    display_name: str
    source_ref: Optional[str]
    source_pinned: bool = True
    endpoint: Optional[str] = None
    include_tools: tuple[str, ...] = ()
    exclude_tools: tuple[str, ...] = ()
    resources_enabled: bool = False
    prompts_enabled: bool = False

    @field_validator("include_tools", "exclude_tools", mode="before")
    @classmethod
    def _coerce_tools(cls, value: JsonValue) -> JsonValue | tuple[str, ...]:
        if isinstance(value, list):
            return tuple(value)
        return value


class McpRuntimeDiscoveryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: McpRuntimeDecision
    reason: str
    server_id: str
    transport: McpTransportKind
    manifest: Optional[McpServerManifest] = None
    discovered_tool_count: int = Field(default=0, ge=0)
    compiled_tools: tuple[McpToolManifest, ...] = ()
    request_count: int = Field(default=0, ge=0)
    handler_executed: bool = False
    network_opened: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True


__all__ = [
    "McpDiscoveryClient",
    "McpRuntimeDecision",
    "McpRuntimeDiscoveryResult",
    "McpRuntimeServerSpec",
    "McpTransportKind",
]
