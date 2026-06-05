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


def test_live_research_evidence_graph_builds_source_pinned_graph() -> None:
    result = LiveResearchEvidenceGraphRuntime().build(
        external_result=_research_external_result(),
        graph_ref="research-graph://wave142/github",
        objective_id="wave142.objective",
    )

    assert result.decision == "graph_ready"
    assert result.external_result_bound is True
    assert result.graph_created is True
    assert result.source_id == "github"
    assert result.graph_node_count == 2
    assert result.external_claims_pinned is True
    assert result.external_network_seen is True
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.no_secret_echo is True
    assert result.live_production_claimed is False
    assert result.graph_payload is not None
    assert result.graph_payload["nodes"][0]["source_kind"] == "github_source_pin"


def test_live_research_evidence_graph_blocks_unexecuted_external_result() -> None:
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=LiveResearchActivationPolicyRuntime().plan(
            source_id="github",
            query="parallel coding workflow",
            live_search_requested=True,
            source_pin_ref="source-pin://research/github",
        ),
        client_result=_client_result(),
        execution_ref="research-external://wave142/blocked",
    )

    result = LiveResearchEvidenceGraphRuntime().build(
        external_result=external_result,
        graph_ref="research-graph://wave142/blocked",
        objective_id="wave142.objective",
    )

    assert result.decision == "blocked"
    assert "research_external_execution_not_ready" in result.blocked_reasons
    assert result.graph_created is False
    assert result.network_opened is False


def test_live_research_evidence_graph_blocks_empty_result_items() -> None:
    empty_client = _client_result().model_copy(update={"result_count": 0, "response_payload": {"items": []}})
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=_research_policy(),
        client_result=empty_client,
        execution_ref="research-external://wave142/empty",
    )

    result = LiveResearchEvidenceGraphRuntime().build(
        external_result=external_result,
        graph_ref="research-graph://wave142/empty",
        objective_id="wave142.objective",
    )

    assert result.decision == "blocked"
    assert "research_external_items_required" in result.blocked_reasons
    assert result.graph_payload is None


def test_cli_and_python_library_live_research_evidence_graph() -> None:
    external_result = _research_external_result()
    completed = CliRunner().invoke(
        app,
        [
            "live-research-evidence-graph",
            "--external-result-json",
            external_result.model_dump_json(),
            "--graph-ref",
            "research-graph://wave142/github",
            "--objective-id",
            "wave142.objective",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_evidence_graph(
        external_result.to_payload(),
        graph_ref="research-graph://wave142/github-library",
        objective_id="wave142.objective",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "graph_ready"
    assert payload["graph_node_count"] == 2
    assert payload["network_opened"] is False
    assert library_payload["decision"] == "graph_ready"


def _research_external_result():
    return LiveResearchExternalTransportRuntime().execute(
        policy=_research_policy(),
        client_result=_client_result(),
        execution_ref="research-external://wave142/github",
    )


def _research_policy():
    return LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref="approval://research/github",
        source_pin_ref="source-pin://research/github",
        max_results=5,
        rate_limit_per_minute=30,
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
            "debug": "token=ghp_" + "wave142",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="research-external-client-closed",
    )
