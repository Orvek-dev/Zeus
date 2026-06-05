from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowOntologyRegistryDecision = Literal["workflow_recorded", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowOntologyRegistryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowOntologyRegistryDecision
    record_id: Optional[str]
    record_ref: Optional[str]
    record_path: str
    workflow_ingestion_id: Optional[str]
    candidate_id: Optional[str]
    candidate_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    workflow_ingestion_bound: bool = False
    ontology_registry_bound: bool = False
    record_count: int = 0
    registry_result: Optional[dict[str, JsonValue]] = None
    promoted: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
