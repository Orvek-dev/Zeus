from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphRuntime
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientTransportRuntime,
    StaticResearchOwnedClient,
)
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave148_live_research_owned_client_transport import _receipt


def test_live_research_evidence_graph_absorbs_owned_client_result() -> None:
    owned_result = _owned_result()

    result = LiveResearchEvidenceGraphRuntime().build(
        owned_client_result=owned_result,
        graph_ref="research-graph://wave149/github-owned",
        objective_id="wave149.objective",
    )

    assert result.decision == "graph_ready"
    assert result.owned_client_result_bound is True
    assert result.external_result_bound is True
    assert result.graph_created is True
    assert result.source_id == "github"
    assert result.graph_node_count == 1
    assert result.external_network_seen is True
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_research_evidence_graph_blocks_unexecuted_owned_client_result() -> None:
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )
    owned_result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=StaticResearchOwnedClient(_receipt()),
        execution_ref="research-owned-client://wave149/policy-block",
    )

    result = LiveResearchEvidenceGraphRuntime().build(
        owned_client_result=owned_result,
        graph_ref="research-graph://wave149/blocked",
        objective_id="wave149.objective",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_not_executed" in result.blocked_reasons
    assert result.graph_created is False
    assert result.network_opened is False


def test_cli_and_python_library_owned_client_graph_absorption() -> None:
    owned_result = _owned_result()
    completed = CliRunner().invoke(
        app,
        [
            "live-research-evidence-graph",
            "--owned-client-result-json",
            owned_result.model_dump_json(),
            "--graph-ref",
            "research-graph://wave149/github-owned",
            "--objective-id",
            "wave149.objective",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_evidence_graph(
        owned_client_result=owned_result.to_payload(),
        graph_ref="research-graph://wave149/github-owned-library",
        objective_id="wave149.objective",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "graph_ready"
    assert payload["owned_client_result_bound"] is True
    assert payload["graph_node_count"] == 1
    assert payload["network_opened"] is False
    assert library_payload["decision"] == "graph_ready"


def _owned_result():
    return LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=StaticResearchOwnedClient(_receipt()),
        execution_ref="research-owned-client://wave149/github",
    )
