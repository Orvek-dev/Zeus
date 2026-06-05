from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

LiveGatewayCredentialedHttpDecision = Literal["executed", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveGatewayCredentialedHttpResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayCredentialedHttpDecision
    execution_id: Optional[str]
    release_id: Optional[str]
    injection_id: Optional[str]
    material_proof_id: Optional[str]
    delivery_envelope_id: Optional[str]
    body_id: Optional[str]
    delivery_endpoint: Optional[str]
    delivery_endpoint_host: Optional[str]
    execution_ref: Optional[str]
    release_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    gateway_credentialed_http: bool = False
    sealed_credential_bound: bool = False
    gateway_envelope_bound: bool = False
    gateway_delivery_body_bound: bool = False
    local_http_loopback: bool = False
    delivery_attempted: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    material_released_to_consumer: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
