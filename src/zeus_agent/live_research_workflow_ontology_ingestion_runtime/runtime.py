from __future__ import annotations

import json
from typing import Final, Optional

from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_ontology_ingestion_runtime import (
    LiveResearchOntologyIngestionResult,
    LiveResearchOntologyIngestionRuntime,
)
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphResult,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime.models import (
    LiveResearchWorkflowOntologyIngestionResult,
    ResearchWorkflowOntologyIngestionDecision,
)

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowOntologyIngestionRuntime:
    def propose(
        self,
        *,
        workflow_graph: LiveResearchWorkflowEvidenceGraphResult,
        candidate_ref: str,
        term: str,
        definition: str,
    ) -> LiveResearchWorkflowOntologyIngestionResult:
        graph_result = _graph_result(workflow_graph)
        ingestion = LiveResearchOntologyIngestionRuntime().propose(
            graph_result=graph_result,
            candidate_ref=candidate_ref,
            term=term,
            definition=definition,
        )
        reasons = list(_workflow_graph_reasons(workflow_graph, graph_result))
        reasons.extend(_ingestion_reasons(ingestion))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowOntologyIngestionDecision = (
            "blocked" if blocked_reasons else "workflow_candidate_proposed"
        )
        ready = decision == "workflow_candidate_proposed"
        result = LiveResearchWorkflowOntologyIngestionResult(
            decision=decision,
            ingestion_id=ingestion.ingestion_id if ready else None,
            workflow_graph_id=workflow_graph.graph_id,
            graph_id=ingestion.graph_id,
            candidate_id=ingestion.candidate_id if ready else None,
            candidate_ref=ingestion.candidate_ref,
            term=ingestion.term,
            blocked_reasons=blocked_reasons,
            workflow_graph_bound=ready,
            ontology_ingestion_bound=ready,
            candidate_proposed=ready,
            provenance_count=ingestion.provenance_count if ready else 0,
            ingestion_result=ingestion.to_payload() if ready else None,
            promoted=False,
            active_rule_written=False,
            authority_widened=False,
            network_opened=False,
            handler_executed=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _graph_result(
    workflow_graph: LiveResearchWorkflowEvidenceGraphResult,
) -> Optional[LiveResearchEvidenceGraphResult]:
    if workflow_graph.graph_result is None:
        return None
    return LiveResearchEvidenceGraphResult.model_validate(workflow_graph.graph_result)


def _workflow_graph_reasons(
    workflow_graph: LiveResearchWorkflowEvidenceGraphResult,
    graph_result: Optional[LiveResearchEvidenceGraphResult],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if workflow_graph.decision != "workflow_graph_ready" or not workflow_graph.graph_created:
        reasons.append("research_workflow_graph_not_ready")
    if graph_result is None:
        reasons.append("research_workflow_graph_result_required")
    if workflow_graph.network_opened or workflow_graph.credential_material_accessed:
        reasons.append("research_workflow_ontology_graph_side_effect_detected")
    if not workflow_graph.no_secret_echo or workflow_graph.live_production_claimed:
        reasons.append("research_workflow_ontology_graph_secret_or_production_claim")
    return tuple(dict.fromkeys(reasons))


def _ingestion_reasons(ingestion: LiveResearchOntologyIngestionResult) -> tuple[str, ...]:
    if ingestion.decision == "candidate_proposed":
        return ()
    return tuple("research_workflow_ontology:{0}".format(reason) for reason in ingestion.blocked_reasons)


def _recommended_next_commands(
    decision: ResearchWorkflowOntologyIngestionDecision,
) -> tuple[str, ...]:
    if decision == "workflow_candidate_proposed":
        return ("zeus live-research-ontology-record --json", "zeus live --json")
    return (
        "zeus live-research-workflow-evidence-graph --json",
        "zeus live-research-ontology-ingestion --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowOntologyIngestionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
