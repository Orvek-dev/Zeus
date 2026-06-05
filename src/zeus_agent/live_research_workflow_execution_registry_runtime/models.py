from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ResearchWorkflowExecutionRegistryDecision = Literal["recorded", "listed", "deleted", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExecutionRegistryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExecutionRegistryDecision
    record_id: Optional[str] = None
    record_ref: Optional[str] = None
    record_path: str
    status_id: Optional[str] = None
    workflow_execution_id: Optional[str] = None
    execution_kind: Optional[Literal["loopback", "external"]] = None
    record_count: int = 0
    loopback_execution_record_count: int = 0
    external_execution_record_count: int = 0
    deleted_count: int = 0
    records: tuple[dict[str, JsonValue], ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = ()
    external_network_seen: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
