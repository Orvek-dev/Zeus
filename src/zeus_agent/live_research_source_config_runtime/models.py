from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchSourceConfigResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["configured", "blocked"]
    config_id: Optional[str]
    adapter_id: str
    source_id: Optional[str]
    endpoint: Optional[str]
    default_endpoint_used: bool = False
    endpoint_config_required: bool = False
    adapter_bound: bool = False
    endpoint_bound: bool = False
    loopback_endpoint: bool = False
    non_loopback_endpoint: bool = False
    credential_scope: Optional[str] = None
    credential_material_accessed: bool = False
    real_fetcher_available: bool = False
    production_fetcher_configured: bool = False
    network_opened: bool = False
    live_production_claimed: bool = False
    blocked_reasons: tuple[str, ...] = ()
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
