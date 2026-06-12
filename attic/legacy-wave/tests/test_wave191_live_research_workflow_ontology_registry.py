from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)
from tests.test_wave190_live_research_workflow_ontology_ingestion import _workflow_graph
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionRuntime,
)


def test_workflow_ontology_registry_records_workflow_candidate(tmp_path: Path) -> None:
    ingestion = _workflow_ingestion("recorded")

    result = LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave191/workflow",
    )

    assert result.decision == "workflow_recorded"
    assert result.record_id is not None
    assert result.workflow_ingestion_bound is True
    assert result.ontology_registry_bound is True
    assert result.record_count == 1
    assert result.promoted is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_workflow_ontology_registry_blocks_unready_workflow_ingestion(tmp_path: Path) -> None:
    blocked = _workflow_ingestion("blocked").model_copy(
        update={"decision": "blocked", "ingestion_result": None}
    )

    result = LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=blocked,
        record_ref="ontology-candidate-record://wave191/blocked",
    )

    assert result.decision == "blocked"
    assert "research_workflow_ontology_candidate_not_proposed" in result.blocked_reasons
    assert "research_workflow_ontology_ingestion_result_required" in result.blocked_reasons
    assert result.record_count == 0
    assert result.network_opened is False


def test_workflow_ontology_registry_cli_and_library_surface_match(tmp_path: Path) -> None:
    ingestion = _workflow_ingestion("cli")
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-research-workflow-ontology-record",
            "--home",
            str(tmp_path),
            "--workflow-ingestion-json",
            ingestion.model_dump_json(),
            "--record-ref",
            "ontology-candidate-record://wave191/cli",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_research_workflow_ontology_record(
        workflow_ingestion=ingestion.to_payload(),
        record_ref="ontology-candidate-record://wave191/library",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["decision"] == "workflow_recorded"
    assert cli_payload["network_opened"] is False
    assert library_payload["decision"] == "workflow_recorded"
    assert library_payload["record_count"] == 2


def _workflow_ingestion(tag: str):
    return LiveResearchWorkflowOntologyIngestionRuntime().propose(
        workflow_graph=_workflow_graph("registry-{0}".format(tag)),
        candidate_ref="ontology-candidate://wave191/{0}".format(tag),
        term="workflow_live_research_source",
        definition="Source-pinned workflow live research output usable by Zeus planning.",
    )
