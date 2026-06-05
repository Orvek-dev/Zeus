from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowEvidenceGraphDecision = Literal["workflow_graph_ready", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowEvidenceGraphResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowEvidenceGraphDecision
    graph_id: Optional[str]
    graph_ref: Optional[str]
    objective_id: Optional[str]
    workflow_execution_id: Optional[str]
    external_transport_execution_id: Optional[str]
    source_id: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    workflow_external_execution_bound: bool = False
    external_result_bound: bool = False
    graph_result_bound: bool = False
    graph_created: bool = False
    graph_node_count: int = 0
    graph_edge_count: int = 0
    external_network_seen: bool = False
    graph_result: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
