from __future__ import annotations

from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)
from tests.test_wave191_live_research_workflow_ontology_registry import _workflow_ingestion


def test_zeus_agent_growth_facade_exposes_skill_eval_from_local_home(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "library")
    agent = ZeusAgent(home=tmp_path)

    skill_eval = agent.skill_eval(candidate_id=registry.candidate_id or "")
    skill_status = agent.skill_status(candidate_id=registry.candidate_id)
    ontology_status = agent.ontology_status(candidate_id=registry.candidate_id)
    persona_status = agent.persona_status()

    assert skill_eval["decision"] == "evaluated"
    assert skill_eval["eval_status"] == "ready_for_review"
    assert skill_eval["source"] == "ontology_review_queue"
    assert skill_eval["promotion_allowed"] is False
    assert skill_status["selected_candidate"]["source"] == "ontology_review_queue"
    assert ontology_status["selected_candidate"]["source"] == "live_research_ontology_registry"
    assert persona_status["decision"] == "report"


def _record_workflow_candidate(tmp_path: Path, tag: str):
    ingestion = _workflow_ingestion("wave197-{0}".format(tag))
    return LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave197/{0}".format(tag),
    )
