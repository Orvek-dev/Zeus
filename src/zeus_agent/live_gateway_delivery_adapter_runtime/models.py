from __future__ import annotations

from typing import Final, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

GatewayDeliveryAdapterTransportKind = Literal["external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveGatewayDeliveryAdapterRequest(BaseModel):
    model_config = _MODEL_CONFIG

    adapter_id: str
    target: str
    delivery_envelope_id: str
    production_claim_id: str
    production_approval_id: str
    header_name: str
    header_value_ref: str
    message_digest: str
    idempotency_key: str
    timeout_ms: int
    retry_attempts: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveGatewayDeliveryAdapterReceipt(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    external_delivery_opened: bool = True
    cleanup_receipt: str = "gateway-delivery-adapter-client-closed"


class LiveGatewayDeliveryAdapterClient(Protocol):
    def deliver(self, request: LiveGatewayDeliveryAdapterRequest) -> LiveGatewayDeliveryAdapterReceipt:
        ...


class StaticGatewayDeliveryAdapterClient:
    def __init__(self, receipt: LiveGatewayDeliveryAdapterReceipt) -> None:
        self.receipt = receipt

    def deliver(self, request: LiveGatewayDeliveryAdapterRequest) -> LiveGatewayDeliveryAdapterReceipt:
        return self.receipt


class LiveGatewayDeliveryAdapterResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["executed", "blocked"]
    execution_id: Optional[str]
    claim_id: Optional[str]
    production_approval_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    handoff_id: Optional[str]
    credential_injection_id: Optional[str]
    delivery_envelope_id: Optional[str]
    transport_kind: Optional[GatewayDeliveryAdapterTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    gateway_delivery_adapter: bool = False
    production_claim_bound: bool = False
    credential_injection_bound: bool = False
    request_constructed: bool = False
    header_value_ref_bound: bool = False
    policy_bound: bool = False
    preflight_bound: bool = False
    gateway_envelope_bound: bool = False
    credential_handoff_bound: bool = False
    remote_executor_preflight_bound: bool = False
    remote_target_bound: bool = False
    delivery_attempted: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    external_delivery_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
