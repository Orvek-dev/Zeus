from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_registry_runtime import (
    LiveResearchOntologyRegistryResult,
    LiveResearchOntologyRegistryRuntime,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionResult,
)
from zeus_agent.live_research_workflow_ontology_registry_runtime.models import (
    LiveResearchWorkflowOntologyRegistryResult,
    ResearchWorkflowOntologyRegistryDecision,
)

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowOntologyRegistryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(
        self,
        *,
        workflow_ingestion: LiveResearchWorkflowOntologyIngestionResult,
        record_ref: str,
    ) -> LiveResearchWorkflowOntologyRegistryResult:
        ingestion = _ingestion_result(workflow_ingestion)
        registry = (
            _blocked_registry(self.home)
            if ingestion is None
            else LiveResearchOntologyRegistryRuntime(self.home).record(
                ingestion=ingestion,
                record_ref=record_ref,
            )
        )
        reasons = list(_workflow_reasons(workflow_ingestion, ingestion))
        reasons.extend(_registry_reasons(registry))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowOntologyRegistryDecision = (
            "blocked" if blocked_reasons else "workflow_recorded"
        )
        ready = decision == "workflow_recorded"
        result = LiveResearchWorkflowOntologyRegistryResult(
            decision=decision,
            record_id=registry.record_id if ready else None,
            record_ref=registry.record_ref,
            record_path=registry.record_path,
            workflow_ingestion_id=workflow_ingestion.ingestion_id,
            candidate_id=registry.candidate_id if ready else None,
            candidate_ref=registry.candidate_ref,
            blocked_reasons=blocked_reasons,
            workflow_ingestion_bound=ready,
            ontology_registry_bound=ready,
            record_count=registry.record_count if ready else 0,
            registry_result=registry.to_payload() if ready else None,
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


def _ingestion_result(
    workflow_ingestion: LiveResearchWorkflowOntologyIngestionResult,
) -> Optional[LiveResearchOntologyIngestionResult]:
    if workflow_ingestion.ingestion_result is None:
        return None
    return LiveResearchOntologyIngestionResult.model_validate(workflow_ingestion.ingestion_result)


def _workflow_reasons(
    workflow_ingestion: LiveResearchWorkflowOntologyIngestionResult,
    ingestion: Optional[LiveResearchOntologyIngestionResult],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if workflow_ingestion.decision != "workflow_candidate_proposed":
        reasons.append("research_workflow_ontology_candidate_not_proposed")
    if ingestion is None:
        reasons.append("research_workflow_ontology_ingestion_result_required")
    if workflow_ingestion.promoted or workflow_ingestion.active_rule_written or workflow_ingestion.authority_widened:
        reasons.append("research_workflow_ontology_promotion_detected")
    if workflow_ingestion.network_opened or workflow_ingestion.credential_material_accessed:
        reasons.append("research_workflow_ontology_registry_side_effect_detected")
    if not workflow_ingestion.no_secret_echo or workflow_ingestion.live_production_claimed:
        reasons.append("research_workflow_ontology_secret_or_production_claim")
    return tuple(dict.fromkeys(reasons))


def _registry_reasons(registry: LiveResearchOntologyRegistryResult) -> tuple[str, ...]:
    if registry.decision == "recorded":
        return ()
    return tuple("research_workflow_ontology_registry:{0}".format(reason) for reason in registry.blocked_reasons)


def _blocked_registry(home: Path) -> LiveResearchOntologyRegistryResult:
    return LiveResearchOntologyRegistryResult(
        decision="blocked",
        record_path=str(home / "ontology" / "live-research-candidates.jsonl"),
        blocked_reasons=("research_workflow_ontology_ingestion_result_required",),
    )


def _recommended_next_commands(
    decision: ResearchWorkflowOntologyRegistryDecision,
) -> tuple[str, ...]:
    if decision == "workflow_recorded":
        return ("zeus live-research-ontology-records --json", "zeus ontology --json")
    return (
        "zeus live-research-workflow-ontology-ingestion --json",
        "zeus live-research-ontology-record --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowOntologyRegistryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
