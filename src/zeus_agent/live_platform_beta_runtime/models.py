from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

LivePlatformBetaDecision = Literal["report", "blocked"]
LivePlatformBetaScenario = Literal["status", "operator-demo", "public-boundary"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class LivePlatformBetaResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LivePlatformBetaDecision
    target_version: Literal["v5.0.0"] = "v5.0.0"
    scenario: LivePlatformBetaScenario
    blocked_reasons: tuple[str, ...] = ()
    zeus_call_response: str = "네, 제우스입니다."
    productized_live_platform_beta_ready: bool = False
    objective_execution_spine_ready: bool = False
    governed_live_slice_ready: bool = False
    authority_ux_ready: bool = False
    operator_journey_ready: bool = False
    public_beta_boundary_ready: bool = False
    cli_surface_ready: bool = False
    python_library_surface_ready: bool = False
    productized_platform_ready: bool = False
    status_cockpit_ready: bool = False
    setup_wizard_ready: bool = False
    operator_commands: tuple[str, ...] = ()
    external_provider_enabled: bool = False
    remote_mcp_enabled: bool = False
    remote_sandbox_enabled: bool = False
    production_ready: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    @field_validator("blocked_reasons", "operator_commands")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
