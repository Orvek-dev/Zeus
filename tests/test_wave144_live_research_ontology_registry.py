from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphRuntime
from zeus_agent.live_research_external_transport_runtime import (
    LiveResearchExternalClientResult,
    LiveResearchExternalTransportRuntime,
)
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionRuntime
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime


def test_live_research_ontology_registry_records_and_lists_candidate(tmp_path: Path) -> None:
    runtime = LiveResearchOntologyRegistryRuntime(tmp_path)
    recorded = runtime.record(
        ingestion=_ingestion(),
        record_ref="ontology-candidate-record://wave144/live-research-source",
    )
    listed = runtime.list()

    assert recorded.decision == "recorded"
    assert recorded.record_id is not None
    assert recorded.candidate_storage_mode == "local_review_only"
    assert recorded.record_count == 1
    assert listed.decision == "listed"
    assert listed.record_count == 1
    assert listed.records[0]["candidate_status"] == "proposed_not_promoted"
    assert listed.network_opened is False
    assert listed.live_production_claimed is False


def test_live_research_ontology_registry_blocks_promotion_state(tmp_path: Path) -> None:
    unsafe = _ingestion().model_copy(
        update={"promoted": True, "candidate_status": "approved_for_promotion"},
    )
    runtime = LiveResearchOntologyRegistryRuntime(tmp_path)

    result = runtime.record(
        ingestion=unsafe,
        record_ref="ontology-candidate-record://wave144/unsafe",
    )

    assert result.decision == "blocked"
    assert "ontology_candidate_promotion_detected" in result.blocked_reasons
    assert runtime.list().record_count == 0


def test_cli_and_python_library_live_research_ontology_registry(tmp_path: Path) -> None:
    ingestion = _ingestion()
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "live-research-ontology-record",
            "--home",
            str(tmp_path),
            "--ingestion-json",
            ingestion.model_dump_json(),
            "--record-ref",
            "ontology-candidate-record://wave144/cli",
            "--json",
        ],
    )
    listed = runner.invoke(
        app,
        ["live-research-ontology-records", "--home", str(tmp_path), "--json"],
    )

    assert completed.exit_code == 0, completed.stdout
    assert listed.exit_code == 0, listed.stdout
    assert json.loads(completed.stdout)["decision"] == "recorded"
    assert json.loads(listed.stdout)["record_count"] == 1

    library_recorded = ZeusAgent(home=tmp_path).live_research_ontology_record(
        ingestion.to_payload(),
        record_ref="ontology-candidate-record://wave144/library",
    )
    library_list = ZeusAgent(home=tmp_path).live_research_ontology_records()
    assert library_recorded["decision"] == "recorded"
    assert library_list["record_count"] == 2


def _ingestion():
    return LiveResearchOntologyIngestionRuntime().propose(
        graph_result=LiveResearchEvidenceGraphRuntime().build(
            external_result=LiveResearchExternalTransportRuntime().execute(
                policy=LiveResearchActivationPolicyRuntime().plan(
                    source_id="github",
                    query="parallel coding workflow",
                    live_search_requested=True,
                    approval_ref="approval://research/github",
                    source_pin_ref="source-pin://research/github",
                    max_results=5,
                    rate_limit_per_minute=30,
                ),
                client_result=_client_result(),
                execution_ref="research-external://wave144/github",
            ),
            graph_ref="research-graph://wave144/github",
            objective_id="wave144.objective",
        ),
        candidate_ref="ontology-candidate://wave144/live-research-source",
        term="live_research_source",
        definition="Source-pinned live research output usable by Zeus planning.",
    )


def _client_result() -> LiveResearchExternalClientResult:
    return LiveResearchExternalClientResult(
        status_code=200,
        latency_ms=52,
        source_pin_ref="source-pin://research/github",
        result_count=1,
        response_payload={
            "items": [
                {"title": "Orvek-dev/Zeus", "url": "https://github.com/Orvek-dev/Zeus"},
            ],
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="research-external-client-closed",
    )
