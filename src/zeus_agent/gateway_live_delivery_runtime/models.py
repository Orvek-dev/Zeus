from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

GatewayLiveDeliveryDecision = Literal["report", "blocked"]
GatewayLiveDeliveryScenario = Literal["status", "loopback-smoke", "blocked-target"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)


class GatewayLiveDeliveryContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: GatewayLiveDeliveryDecision
    target_version: str
    release_stage: Literal["gateway_live_delivery"]
    objective_contract_id: str
    scenario: GatewayLiveDeliveryScenario
    blocked_reasons: tuple[str, ...] = ()
    gateway_live_delivery_contract_available: bool = True
    gateway_settings_available: bool = True
    gateway_pairing_available: bool = True
    gateway_delivery_envelope_available: bool = True
    gateway_delivery_body_available: bool = True
    gateway_loopback_transport_available: bool = True
    gateway_loopback_http_available: bool = True
    gateway_external_delivery_available: bool = False
    gateway_webhook_available: bool = False
    gateway_live_delivery_ready: bool = False
    production_ready: bool = False
    gateway_smoke: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> GatewayLiveDeliveryContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        return self.model_copy(update={"no_secret_echo": not any(marker in serialized for marker in _SECRET_MARKERS)})
