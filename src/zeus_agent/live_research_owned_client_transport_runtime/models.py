from __future__ import annotations

from typing import Final, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult

ResearchOwnedClientTransportKind = Literal["owned_external_search"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchOwnedClientRequest(BaseModel):
    model_config = _MODEL_CONFIG

    policy_id: str
    source_id: str
    query: str
    source_pin_ref: str
    max_results: int
    rate_limit_per_minute: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchOwnedClientReceipt(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    source_pin_ref: str
    result_count: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    cleanup_receipt: str = "research-owned-client-closed"


class LiveResearchOwnedClient(Protocol):
    def search(self, request: LiveResearchOwnedClientRequest) -> LiveResearchOwnedClientReceipt:
        ...


class StaticResearchOwnedClient:
    def __init__(self, receipt: LiveResearchOwnedClientReceipt) -> None:
        self.receipt = receipt

    def search(self, request: LiveResearchOwnedClientRequest) -> LiveResearchOwnedClientReceipt:
        return self.receipt


class LiveResearchOwnedClientTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["executed", "blocked"]
    execution_id: Optional[str]
    policy_id: Optional[str]
    source_id: Optional[str]
    source_pin_ref: Optional[str]
    transport_kind: Optional[ResearchOwnedClientTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    research_owned_client: bool = False
    request_constructed: bool = False
    policy_bound: bool = False
    source_pin_bound: bool = False
    research_invoked: bool = False
    live_search_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None
    external_transport_result: Optional[LiveResearchExternalTransportResult] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
