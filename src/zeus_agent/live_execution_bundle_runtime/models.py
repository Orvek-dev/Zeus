from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

LiveExecutionBundleDecision = Literal["summarized", "blocked"]
LiveExecutionSurfaceKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveExecutionSurfaceSummary(BaseModel):
    model_config = _MODEL_CONFIG

    surface_kind: LiveExecutionSurfaceKind
    decision: Literal["executed", "blocked"]
    execution_id: Optional[str]
    release_id: Optional[str]
    body_id: Optional[str]
    endpoint_host: Optional[str]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    status_code: Optional[int] = None
    local_http_loopback: bool = False
    credentialed_http: bool = False
    sealed_credential_bound: bool = False
    material_released_to_consumer: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False


class LiveExecutionBundleResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionBundleDecision
    bundle_id: Optional[str]
    bundle_ref: str
    surfaces: tuple[LiveExecutionSurfaceSummary, ...] = ()
    surface_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    local_loopback_count: int = 0
    credentialed_surface_count: int = 0
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    safety_notes: tuple[str, ...] = Field(default_factory=tuple)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
