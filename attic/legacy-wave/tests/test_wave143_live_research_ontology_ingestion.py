from __future__ import annotations

import json

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


def test_live_research_ontology_ingestion_proposes_candidate_without_promotion() -> None:
    result = LiveResearchOntologyIngestionRuntime().propose(
        graph_result=_research_graph(),
        candidate_ref="ontology-candidate://wave143/live-research-source",
        term="live_research_source",
        definition="Source-pinned live research output usable by Zeus planning.",
    )

    assert result.decision == "candidate_proposed"
    assert result.graph_result_bound is True
    assert result.candidate_proposed is True
    assert result.candidate_status == "proposed_not_promoted"
    assert result.provenance_count == 2
    assert result.promoted is False
    assert result.ontology_term_promoted is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.no_secret_echo is True
    assert result.live_production_claimed is False


def test_live_research_ontology_ingestion_blocks_unready_graph() -> None:
    graph = _research_graph().model_copy(update={"decision": "blocked", "graph_created": False})

    result = LiveResearchOntologyIngestionRuntime().propose(
        graph_result=graph,
        candidate_ref="ontology-candidate://wave143/blocked",
        term="live_research_source",
        definition="Source-pinned live research output usable by Zeus planning.",
    )

    assert result.decision == "blocked"
    assert "research_graph_not_ready" in result.blocked_reasons
    assert result.candidate_proposed is False
    assert result.network_opened is False


def test_live_research_ontology_ingestion_blocks_secret_like_term_content() -> None:
    result = LiveResearchOntologyIngestionRuntime().propose(
        graph_result=_research_graph(),
        candidate_ref="ontology-candidate://wave143/secret",
        term="live_research_source",
        definition="Do not store secret=sk-" + "wave143 in ontology.",
    )

    assert result.decision == "blocked"
    assert "ontology_candidate_build_failed" in result.blocked_reasons
    assert result.candidate_payload is None
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_research_ontology_ingestion() -> None:
    graph = _research_graph()
    completed = CliRunner().invoke(
        app,
        [
            "live-research-ontology-ingestion",
            "--graph-result-json",
            graph.model_dump_json(),
            "--candidate-ref",
            "ontology-candidate://wave143/live-research-source",
            "--term",
            "live_research_source",
            "--definition",
            "Source-pinned live research output usable by Zeus planning.",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_ontology_ingestion(
        graph.to_payload(),
        candidate_ref="ontology-candidate://wave143/live-research-source-library",
        term="live_research_source",
        definition="Source-pinned live research output usable by Zeus planning.",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "candidate_proposed"
    assert payload["candidate_status"] == "proposed_not_promoted"
    assert payload["promoted"] is False
    assert library_payload["decision"] == "candidate_proposed"


def _research_graph():
    return LiveResearchEvidenceGraphRuntime().build(
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
            execution_ref="research-external://wave143/github",
        ),
        graph_ref="research-graph://wave143/github",
        objective_id="wave143.objective",
    )


def _client_result() -> LiveResearchExternalClientResult:
    return LiveResearchExternalClientResult(
        status_code=200,
        latency_ms=52,
        source_pin_ref="source-pin://research/github",
        result_count=2,
        response_payload={
            "items": [
                {"title": "Orvek-dev/Zeus", "url": "https://github.com/Orvek-dev/Zeus"},
                {"title": "NousResearch/hermes-agent", "url": "https://github.com/NousResearch/hermes-agent"},
            ],
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="research-external-client-closed",
    )
