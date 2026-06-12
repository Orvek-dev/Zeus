from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphRuntime
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionRuntime
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime
from tests.test_wave142_live_research_evidence_graph import _research_external_result, _research_policy


def test_live_research_status_reports_recorded_chain(tmp_path: Path) -> None:
    policy, external, graph, ingestion, record = _chain(tmp_path)

    result = LiveResearchStatusRuntime().build(
        policy=policy,
        external_result=external,
        graph_result=graph,
        ingestion=ingestion,
        registry_record=record,
    )

    assert result.decision == "recorded"
    assert result.policy_bound is True
    assert result.external_result_bound is True
    assert result.graph_result_bound is True
    assert result.ontology_candidate_bound is True
    assert result.ontology_recorded is True
    assert result.external_network_seen is True
    assert result.production_ready is False
    assert result.network_opened is False
    assert result.no_secret_echo is True
    assert result.live_production_claimed is False


def test_live_research_status_reports_policy_ready_stage() -> None:
    policy, _, _, _, _ = _chain(None)

    result = LiveResearchStatusRuntime().build(
        policy=policy,
        external_result=None,
        graph_result=None,
        ingestion=None,
        registry_record=None,
    )

    assert result.decision == "policy_ready"
    assert result.policy_bound is True
    assert result.external_result_bound is False
    assert "zeus live-research-external-transport --json" in result.recommended_next_commands


def test_live_research_status_blocks_mismatched_record(tmp_path: Path) -> None:
    policy, external, graph, ingestion, record = _chain(tmp_path)
    mismatched = record.model_copy(update={"candidate_id": "wrong-candidate"})

    result = LiveResearchStatusRuntime().build(
        policy=policy,
        external_result=external,
        graph_result=graph,
        ingestion=ingestion,
        registry_record=mismatched,
    )

    assert result.decision == "blocked"
    assert "ontology_record_candidate_mismatch" in result.blocked_reasons
    assert result.production_ready is False


def test_cli_and_python_library_live_research_status(tmp_path: Path) -> None:
    policy, external, graph, ingestion, record = _chain(tmp_path)

    completed = CliRunner().invoke(
        app,
        [
            "live-research-status",
            "--policy-json",
            policy.model_dump_json(),
            "--external-result-json",
            external.model_dump_json(),
            "--graph-result-json",
            graph.model_dump_json(),
            "--ingestion-json",
            ingestion.model_dump_json(),
            "--registry-record-json",
            record.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_status(
        policy=policy.to_payload(),
        external_result=external.to_payload(),
        graph_result=graph.to_payload(),
        ingestion=ingestion.to_payload(),
        registry_record=record.to_payload(),
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "recorded"
    assert payload["production_ready"] is False
    assert library_payload["decision"] == "recorded"


def _chain(tmp_path: Optional[Path]):
    external = _research_external_result()
    policy = _research_policy()
    graph = LiveResearchEvidenceGraphRuntime().build(
        external_result=external,
        graph_ref="research-graph://wave146/github",
        objective_id="wave146.objective",
    )
    ingestion = LiveResearchOntologyIngestionRuntime().propose(
        graph_result=graph,
        candidate_ref="ontology-candidate://wave146/live-research-source",
        term="live_research_source",
        definition="Source-pinned live research output usable by Zeus planning.",
    )
    registry = None
    if tmp_path is not None:
        registry = LiveResearchOntologyRegistryRuntime(tmp_path).record(
            ingestion=ingestion,
            record_ref="ontology-candidate-record://wave146/status",
        )
    return policy, external, graph, ingestion, registry
