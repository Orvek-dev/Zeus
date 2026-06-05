from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)
from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime
from tests.test_wave191_live_research_workflow_ontology_registry import _workflow_ingestion


def test_skill_cockpit_derives_review_required_candidate_from_ontology_registry(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "skill-proposal")

    result = SkillCockpitRuntime(tmp_path).build(candidate_id=registry.candidate_id)

    assert result.decision == "report"
    assert result.candidate_count == 3
    assert result.ontology_proposal_count == 1
    assert result.review_required_count == 2
    assert result.blocked_candidate_count == 1
    assert result.promoted_candidate_count == 0
    assert result.selected_candidate is not None
    assert result.selected_candidate["source"] == "ontology_review_queue"
    assert result.selected_candidate["source_candidate_id"] == registry.candidate_id
    assert result.selected_candidate["source_record_id"] == registry.record_id
    assert result.selected_candidate["review_status"] == "review_required"
    assert result.selected_candidate["promoted"] is False
    assert result.selected_candidate["active_skill_written"] is False
    assert result.active_skill_written is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_skill_cockpit_ontology_proposal_cli_and_library_surface_match(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "cli")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skills",
            "--home",
            str(tmp_path),
            "--candidate-id",
            registry.candidate_id or "",
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    library_payload = ZeusAgent(home=tmp_path).skill_status(candidate_id=registry.candidate_id)

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "report"
    assert cli_payload["ontology_proposal_count"] == 1
    assert cli_payload["selected_candidate"]["source"] == "ontology_review_queue"
    assert cli_payload["selected_candidate"]["review_status"] == "review_required"
    assert cli_payload["selected_candidate"]["promoted"] is False


def _record_workflow_candidate(tmp_path: Path, tag: str):
    ingestion = _workflow_ingestion("wave194-{0}".format(tag))
    return LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave194/{0}".format(tag),
    )
