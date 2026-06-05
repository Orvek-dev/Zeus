from __future__ import annotations

import json
from typing import Final

from zeus_agent.live_research_evidence_graph_runtime import (
    LiveResearchEvidenceGraphResult,
    LiveResearchEvidenceGraphRuntime,
)
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_workflow_evidence_graph_runtime.models import (
    LiveResearchWorkflowEvidenceGraphResult,
    ResearchWorkflowEvidenceGraphDecision,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowEvidenceGraphRuntime:
    def build(
        self,
        *,
        workflow_external_execution: LiveResearchWorkflowExternalExecutionResult,
        external_result: LiveResearchExternalTransportResult,
        graph_ref: str,
        objective_id: str,
    ) -> LiveResearchWorkflowEvidenceGraphResult:
        graph = LiveResearchEvidenceGraphRuntime().build(
            external_result=external_result,
            graph_ref=graph_ref,
            objective_id=objective_id,
        )
        reasons = list(_workflow_reasons(workflow_external_execution))
        reasons.extend(_match_reasons(workflow_external_execution, external_result))
        reasons.extend(_graph_reasons(graph))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowEvidenceGraphDecision = (
            "blocked" if blocked_reasons else "workflow_graph_ready"
        )
        ready = decision == "workflow_graph_ready"
        result = LiveResearchWorkflowEvidenceGraphResult(
            decision=decision,
            graph_id=graph.graph_id if ready else None,
            graph_ref=graph.graph_ref,
            objective_id=graph.objective_id,
            workflow_execution_id=workflow_external_execution.execution_id,
            external_transport_execution_id=external_result.execution_id,
            source_id=external_result.source_id,
            blocked_reasons=blocked_reasons,
            workflow_external_execution_bound=ready,
            external_result_bound=ready,
            graph_result_bound=ready,
            graph_created=ready and graph.graph_created,
            graph_node_count=graph.graph_node_count if ready else 0,
            graph_edge_count=graph.graph_edge_count if ready else 0,
            external_network_seen=workflow_external_execution.external_network_seen,
            graph_result=graph.to_payload() if ready else None,
            network_opened=False,
            handler_executed=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _workflow_reasons(
    workflow_external_execution: LiveResearchWorkflowExternalExecutionResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if workflow_external_execution.decision != "external_execution_recorded":
        reasons.append("research_workflow_external_execution_not_recorded")
    if not workflow_external_execution.external_result_bound:
        reasons.append("research_workflow_external_execution_result_not_bound")
    if workflow_external_execution.network_opened or workflow_external_execution.live_transport_enabled:
        reasons.append("research_workflow_graph_execution_side_effect_detected")
    if workflow_external_execution.credential_material_accessed or workflow_external_execution.raw_secret_returned:
        reasons.append("research_workflow_graph_execution_secret_leak_detected")
    if not workflow_external_execution.no_secret_echo or workflow_external_execution.live_production_claimed:
        reasons.append("research_workflow_graph_execution_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _match_reasons(
    workflow_external_execution: LiveResearchWorkflowExternalExecutionResult,
    external_result: LiveResearchExternalTransportResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if external_result.execution_id != workflow_external_execution.external_transport_execution_id:
        reasons.append("research_workflow_graph_external_transport_mismatch")
    if external_result.policy_id != workflow_external_execution.policy_id:
        reasons.append("research_workflow_graph_policy_mismatch")
    if external_result.source_id != workflow_external_execution.source_id:
        reasons.append("research_workflow_graph_source_mismatch")
    if external_result.source_pin_ref != workflow_external_execution.source_pin_ref:
        reasons.append("research_workflow_graph_source_pin_mismatch")
    return tuple(dict.fromkeys(reasons))


def _graph_reasons(graph: LiveResearchEvidenceGraphResult) -> tuple[str, ...]:
    if graph.decision == "graph_ready":
        return ()
    return tuple("research_workflow_graph:{0}".format(reason) for reason in graph.blocked_reasons)


def _recommended_next_commands(
    decision: ResearchWorkflowEvidenceGraphDecision,
) -> tuple[str, ...]:
    if decision == "workflow_graph_ready":
        return ("zeus live-research-ontology-ingestion --json", "zeus live --json")
    return (
        "zeus live-research-workflow-external-execution --json",
        "zeus live-research-evidence-graph --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowEvidenceGraphResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
