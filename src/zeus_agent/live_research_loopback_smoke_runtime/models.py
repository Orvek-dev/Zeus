from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchLoopbackSmokeResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["smoke_executed", "blocked"]
    execution_id: Optional[str]
    execution_ref: str
    adapter_id: Optional[str]
    source_id: Optional[str]
    endpoint: Optional[str]
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None
    cleanup_receipt: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    client_constructed: bool = False
    research_invoked: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    external_evidence_ready: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
