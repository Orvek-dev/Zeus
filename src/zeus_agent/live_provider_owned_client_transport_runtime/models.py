from __future__ import annotations

from typing import Final, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

ProviderOwnedClientTransportKind = Literal["external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveProviderOwnedClientRequest(BaseModel):
    model_config = _MODEL_CONFIG

    endpoint: str
    endpoint_host: str
    request_envelope_id: str
    header_name: str
    header_value_ref: str
    body_digest: str
    timeout_ms: int
    retry_attempts: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderOwnedClientReceipt(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    cleanup_receipt: str = "provider-owned-client-closed"


class LiveProviderOwnedClient(Protocol):
    def send(self, request: LiveProviderOwnedClientRequest) -> LiveProviderOwnedClientReceipt:
        ...


class StaticProviderOwnedClient:
    def __init__(self, receipt: LiveProviderOwnedClientReceipt) -> None:
        self.receipt = receipt

    def send(self, request: LiveProviderOwnedClientRequest) -> LiveProviderOwnedClientReceipt:
        return self.receipt


class LiveProviderOwnedClientTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["executed", "blocked"]
    execution_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    handoff_id: Optional[str]
    request_envelope_id: Optional[str]
    transport_kind: Optional[ProviderOwnedClientTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    provider_owned_client: bool = False
    request_constructed: bool = False
    header_value_ref_bound: bool = False
    policy_bound: bool = False
    preflight_bound: bool = False
    provider_envelope_bound: bool = False
    credential_handoff_bound: bool = False
    remote_executor_preflight_bound: bool = False
    remote_target_bound: bool = False
    provider_invoked: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
