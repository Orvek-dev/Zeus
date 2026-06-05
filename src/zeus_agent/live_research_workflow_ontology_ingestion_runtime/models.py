from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowOntologyIngestionDecision = Literal["workflow_candidate_proposed", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowOntologyIngestionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowOntologyIngestionDecision
    ingestion_id: Optional[str]
    workflow_graph_id: Optional[str]
    graph_id: Optional[str]
    candidate_id: Optional[str]
    candidate_ref: Optional[str]
    term: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    workflow_graph_bound: bool = False
    ontology_ingestion_bound: bool = False
    candidate_proposed: bool = False
    provenance_count: int = 0
    ingestion_result: Optional[dict[str, JsonValue]] = None
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
