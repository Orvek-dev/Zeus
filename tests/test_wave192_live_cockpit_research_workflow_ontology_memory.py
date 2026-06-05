from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)
from tests.test_wave191_live_research_workflow_ontology_registry import _workflow_ingestion


def test_live_cockpit_reports_research_workflow_ontology_memory(tmp_path: Path) -> None:
    ingestion = _workflow_ingestion("cockpit-ready")
    registry = LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave192/ready",
    )

    result = LiveCockpitRuntime().build(
        research_workflow_ontology_ingestion=ingestion,
        research_workflow_ontology_registry=registry,
    )

    assert result.decision == "report"
    assert result.research_workflow_ontology_ingestion == ingestion
    assert result.research_workflow_ontology_registry == registry
    assert result.research_workflow_ontology_ingestion_decision == "workflow_candidate_proposed"
    assert result.research_workflow_ontology_ingestion_ready is True
    assert result.research_workflow_ontology_ingestion_ingestion_id == ingestion.ingestion_id
    assert result.research_workflow_ontology_ingestion_candidate_id == ingestion.candidate_id
    assert result.research_workflow_ontology_ingestion_provenance_count == 1
    assert result.research_workflow_ontology_registry_decision == "workflow_recorded"
    assert result.research_workflow_ontology_registry_ready is True
    assert result.research_workflow_ontology_registry_record_id == registry.record_id
    assert result.research_workflow_ontology_registry_candidate_id == registry.candidate_id
    assert result.research_workflow_ontology_registry_record_count == 1
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-ontology-ingestion --json" in result.recommended_next_commands
    assert "zeus live-research-workflow-ontology-record --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_ontology_memory(tmp_path: Path) -> None:
    blocked_ingestion = _workflow_ingestion("cockpit-blocked").model_copy(
        update={
            "decision": "blocked",
            "ingestion_result": None,
            "candidate_proposed": False,
            "blocked_reasons": ("research_workflow_ontology_candidate_not_proposed",),
        }
    )
    blocked_registry = LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=blocked_ingestion,
        record_ref="ontology-candidate-record://wave192/blocked",
    )

    result = LiveCockpitRuntime().build(
        research_workflow_ontology_ingestion=blocked_ingestion,
        research_workflow_ontology_registry=blocked_registry,
    )

    assert result.decision == "blocked"
    assert (
        "research-workflow-ontology-ingestion:"
        "research_workflow_ontology_candidate_not_proposed"
    ) in result.blocked_reasons
    assert (
        "research-workflow-ontology-registry:"
        "research_workflow_ontology_candidate_not_proposed"
    ) in result.blocked_reasons
    assert result.research_workflow_ontology_ingestion_ready is False
    assert result.research_workflow_ontology_registry_ready is False
    assert result.network_opened is False


def test_live_cockpit_ontology_memory_cli_and_library_surface_match(tmp_path: Path) -> None:
    ingestion = _workflow_ingestion("cockpit-cli")
    registry = LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave192/cli",
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--home",
            str(tmp_path),
            "--research-workflow-ontology-ingestion-json",
            ingestion.model_dump_json(),
            "--research-workflow-ontology-registry-json",
            registry.model_dump_json(),
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent(home=tmp_path).live_status(
        research_workflow_ontology_ingestion=ingestion.to_payload(),
        research_workflow_ontology_registry=registry.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_ontology_ingestion_decision"] == "workflow_candidate_proposed"
    assert cli_payload["research_workflow_ontology_registry_decision"] == "workflow_recorded"
    assert cli_payload["network_opened"] is False
