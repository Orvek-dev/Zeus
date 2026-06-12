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
from zeus_agent.ontology_cockpit_runtime import OntologyCockpitRuntime
from tests.test_wave191_live_research_workflow_ontology_registry import _workflow_ingestion


def test_ontology_cockpit_reports_local_registry_review_queue(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "review-queue")

    result = OntologyCockpitRuntime(tmp_path).build(candidate_id=registry.candidate_id)

    assert result.decision == "report"
    assert result.registry_record_count == 1
    assert result.review_queue_count == 1
    assert result.candidate_count == 3
    assert result.proposed_candidate_count == 2
    assert result.blocked_candidate_count == 1
    assert result.promoted_candidate_count == 0
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_id"] == registry.candidate_id
    assert result.selected_candidate["record_id"] == registry.record_id
    assert result.selected_candidate["source"] == "live_research_ontology_registry"
    assert result.selected_candidate["candidate_storage_mode"] == "local_review_only"
    assert result.selected_candidate["promoted"] is False
    assert result.selected_candidate["wiki_page"]["fact_count"] == 0
    assert result.ontology_term_promoted is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_ontology_cockpit_registry_candidate_cli_and_library_surface_match(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "cli")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "ontology",
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
    library_payload = ZeusAgent(home=tmp_path).ontology_status(candidate_id=registry.candidate_id)

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "report"
    assert cli_payload["registry_record_count"] == 1
    assert cli_payload["review_queue_count"] == 1
    assert cli_payload["selected_candidate"]["record_id"] == registry.record_id
    assert cli_payload["selected_candidate"]["candidate_status"] == "proposed_not_promoted"


def _record_workflow_candidate(tmp_path: Path, tag: str):
    ingestion = _workflow_ingestion("wave193-{0}".format(tag))
    return LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave193/{0}".format(tag),
    )
