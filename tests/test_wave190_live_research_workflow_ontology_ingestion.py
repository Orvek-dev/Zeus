from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphRuntime,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionRuntime,
)
from tests.test_wave189_live_research_workflow_evidence_graph import _execution_and_external


def test_workflow_ontology_ingestion_proposes_candidate_from_workflow_graph() -> None:
    workflow_graph = _workflow_graph("ready")

    result = LiveResearchWorkflowOntologyIngestionRuntime().propose(
        workflow_graph=workflow_graph,
        candidate_ref="ontology-candidate://wave190/live-research-source",
        term="workflow_live_research_source",
        definition="Source-pinned workflow live research output usable by Zeus planning.",
    )

    assert result.decision == "workflow_candidate_proposed"
    assert result.workflow_graph_bound is True
    assert result.ontology_ingestion_bound is True
    assert result.candidate_proposed is True
    assert result.provenance_count == 1
    assert result.promoted is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_workflow_ontology_ingestion_blocks_unready_workflow_graph_and_secret_definition() -> None:
    blocked_graph = _workflow_graph("blocked").model_copy(
        update={"decision": "blocked", "graph_created": False}
    )

    result = LiveResearchWorkflowOntologyIngestionRuntime().propose(
        workflow_graph=blocked_graph,
        candidate_ref="ontology-candidate://wave190/blocked",
        term="workflow_live_research_source",
        definition="Do not store secret=sk-" + "wave190.",
    )

    assert result.decision == "blocked"
    assert "research_workflow_graph_not_ready" in result.blocked_reasons
    assert any(reason.startswith("research_workflow_ontology:") for reason in result.blocked_reasons)
    assert result.candidate_proposed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_workflow_ontology_ingestion_cli_and_library_surface_match() -> None:
    workflow_graph = _workflow_graph("cli")
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-ontology-ingestion",
            "--workflow-graph-json",
            workflow_graph.model_dump_json(),
            "--candidate-ref",
            "ontology-candidate://wave190/cli",
            "--term",
            "workflow_live_research_source",
            "--definition",
            "Source-pinned workflow live research output usable by Zeus planning.",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    library_payload = ZeusAgent().live_research_workflow_ontology_ingestion(
        workflow_graph=workflow_graph.to_payload(),
        candidate_ref="ontology-candidate://wave190/cli",
        term="workflow_live_research_source",
        definition="Source-pinned workflow live research output usable by Zeus planning.",
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "workflow_candidate_proposed"
    assert cli_payload["network_opened"] is False


def _workflow_graph(tag: str):
    execution, external_result = _execution_and_external("ontology-{0}".format(tag))
    return LiveResearchWorkflowEvidenceGraphRuntime().build(
        workflow_external_execution=execution,
        external_result=external_result,
        graph_ref="research-workflow-graph://wave190/{0}".format(tag),
        objective_id="wave190.objective",
    )
