from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from zeus_agent.github_runtime import GitHubSourcePin
from zeus_agent.research_runtime import (
    FakeGitHubResearchProvider,
    FakeWebResearchProvider,
    ResearchEvidenceEdge,
    ResearchEvidenceNode,
    ResearchGraphBuilder,
    ResearchProviderQuery,
    ResearchSourcePin,
)
from zeus_agent.wave19_research_provider_scenarios import (
    wave19_research_provider_blocks_payload,
    wave19_research_provider_payload,
)
from zeus_agent.web_runtime import WebSourcePin


def test_fake_web_and_github_providers_build_pinned_research_graph() -> None:
    # Given: fresh pinned web and GitHub source fixtures.
    web = FakeWebResearchProvider(
        provider_id="web.fake",
        sources=(
            WebSourcePin(
                source_id="web.docs.zeus",
                source_url="https://docs.example.test/zeus",
                source_ref="snapshot:2026-06-03T00:00:00Z",
                source_pinned=True,
                freshness="fresh",
                summary="Pinned web source for Zeus connector constraints.",
            ),
        ),
    )
    github = FakeGitHubResearchProvider(
        provider_id="github.fake",
        sources=(
            GitHubSourcePin(
                repo="owner/zeus",
                ref="9f2d4a1",
                query="is:issue label:G005 research provider",
                query_evidence_id="evidence.github.query.001",
                source_pinned=True,
                freshness="fresh",
                summary="Pinned issue query summary.",
            ),
        ),
    )

    # When: fake providers answer a research query and a graph is built.
    query = ResearchProviderQuery(objective_id="g005", query="research provider")
    web_response = web.search(query)
    github_response = github.search(query)
    graph = ResearchGraphBuilder().build(
        nodes=(*web_response.nodes, *github_response.nodes, _local_task_node()),
        edges=(
            ResearchEvidenceEdge(source_node_id="web.docs.zeus", target_node_id="evidence.github.query.001", relation="supports"),
            ResearchEvidenceEdge(source_node_id="evidence.github.query.001", target_node_id="task.g005", relation="verifies"),
            ResearchEvidenceEdge(source_node_id="task.g005", target_node_id="web.docs.zeus", relation="cites"),
        ),
    )

    # Then: graph evidence is source-pinned and no live provider path ran.
    assert web_response.planned_source_count == 1
    assert github_response.planned_source_count == 1
    assert web_response.network_opened is False
    assert github_response.network_opened is False
    assert graph.node_count == 3
    assert graph.edge_count == 3
    assert graph.external_claims_pinned is True
    assert graph.no_secret_echo is True


def test_wave19_happy_payload_proves_fake_provider_research_graph() -> None:
    # Given: the Wave19 happy scenario uses only fake provider sources.
    payload = wave19_research_provider_payload()

    # Then: pinned fresh Web/GitHub sources become a citation graph without live IO.
    assert payload["scenario_id"] == "C001"
    assert payload["web_provider_created"] is True
    assert payload["github_provider_created"] is True
    assert payload["fake_web_provider_called"] is True
    assert payload["fake_github_provider_called"] is True
    assert payload["web_source_planned"] is True
    assert payload["github_source_planned"] is True
    assert payload["source_pins_created"] >= 2
    assert payload["fresh_sources_accepted"] is True
    assert payload["graph_created"] is True
    assert payload["graph_node_count"] >= 3
    assert payload["citation_edge_count"] >= 3
    assert "web.docs.zeus" in payload["provenance_ids"]
    assert "evidence.github.query.001" in payload["provenance_ids"]
    assert payload["external_claims_pinned"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["client_constructed"] is False
    assert payload["subprocess_started"] is False
    assert payload["real_web_adapter_used"] is False
    assert payload["real_github_adapter_used"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_wave19_block_payload_fails_closed_without_secret_echo() -> None:
    # Given: unsafe source pins and graph inputs include stale, unpinned, and secret-like cases.
    raw_secret = "sk-wave19-fixture"

    # When: the block scenario is evaluated.
    payload = wave19_research_provider_blocks_payload(raw_secret=raw_secret)
    serialized = json.dumps(payload, sort_keys=True)

    # Then: all unsafe paths block and the raw secret is absent.
    assert payload["scenario_id"] == "C002"
    assert payload["unpinned_web_source"] == "blocked"
    assert payload["missing_web_source_ref"] == "blocked"
    assert payload["stale_web_source"] == "blocked"
    assert payload["secret_web_summary"] == "blocked"
    assert payload["github_missing_ref"] == "blocked"
    assert payload["github_missing_query_evidence"] == "blocked"
    assert payload["unpinned_github_source"] == "blocked"
    assert payload["stale_github_source"] == "blocked"
    assert payload["secret_github_query"] == "blocked"
    assert payload["stale_graph_source"] == "blocked"
    assert payload["unpinned_graph_external_claim"] == "blocked"
    assert payload["duplicate_graph_node"] == "blocked"
    assert payload["missing_edge_target"] == "blocked"
    assert payload["blocked_handler_executed"] is False
    assert payload["blocked_network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


@pytest.mark.parametrize("source_kind", ("web_source_pin", "github_source_pin"))
def test_research_graph_requires_source_pins_for_web_and_github_claims(source_kind: str) -> None:
    # Given: a web or GitHub graph node reaches the builder without a source pin.
    node = ResearchEvidenceNode(
        node_id="{0}.raw".format(source_kind),
        source_kind=source_kind,
        source_pin=None,
    )

    # When / Then: every non-local source kind is rejected unless pinned.
    with pytest.raises(ValueError, match="external_claims_must_be_pinned"):
        ResearchGraphBuilder().build(nodes=(node,))


def test_research_provider_response_redacts_secret_like_query() -> None:
    # Given: a provider query contains a secret-like value.
    raw_secret = "sk-wave19-review-secret"
    provider = FakeWebResearchProvider(
        provider_id="web.fake",
        sources=(
            WebSourcePin(
                source_id="web.docs.zeus",
                source_url="https://docs.example.test/zeus",
                source_ref="snapshot:2026-06-03T00:00:00Z",
                source_pinned=True,
                freshness="fresh",
                summary="Pinned web source for Zeus connector constraints.",
            ),
        ),
    )

    # When: the fake provider returns a response through the normal surface.
    response = provider.search(
        ResearchProviderQuery(
            objective_id="g005 {0}".format(raw_secret),
            query="research provider {0}".format(raw_secret),
        ),
    )

    # Then: the raw query secret is not echoed in the response payload.
    assert raw_secret not in response.query.objective_id
    assert raw_secret not in response.query.query
    assert response.query.objective_id == "g005 sk-...redacted"
    assert response.query.query == "research provider sk-...redacted"
    assert response.planned_source_count == 1


def test_research_graph_rejects_secret_like_node_id_and_edge_fields() -> None:
    # Given: otherwise valid graph inputs with secret-like node and edge fields.
    pinned = _local_task_node()
    secret_node = ResearchEvidenceNode(
        node_id="sk-wave19-review-secret",
        source_kind="task_evidence_node",
        source_pin=ResearchSourcePin(
            source_type="task_evidence_node",
            source_url="https://tasks.platform.local/evidence/g005",
            source_commit="g005-evidence-node",
            trust_level="high",
            provenance_id="task.pinned.node",
            summary="Task evidence node.",
        ),
    )
    secret_relation = ResearchEvidenceEdge(
        source_node_id="task.g005",
        target_node_id="task.g005",
        relation="sk-wave19-review-secret",
    )
    secret_source_node_id = ResearchEvidenceEdge(
        source_node_id="sk-wave19-review-secret",
        target_node_id="task.g005",
        relation="cites",
    )
    secret_target_node_id = ResearchEvidenceEdge(
        source_node_id="task.g005",
        target_node_id="sk-wave19-review-secret",
        relation="cites",
    )

    # When / Then: the builder blocks secret-like graph identifiers and relations.
    with pytest.raises(ValueError, match="secret_like_graph_field"):
        ResearchGraphBuilder().build(nodes=(secret_node,))
    with pytest.raises(ValueError, match="secret_like_graph_field"):
        ResearchGraphBuilder().build(nodes=(pinned,), edges=(secret_relation,))
    with pytest.raises(ValueError, match="secret_like_graph_field"):
        ResearchGraphBuilder().build(nodes=(pinned,), edges=(secret_source_node_id,))
    with pytest.raises(ValueError, match="secret_like_graph_field"):
        ResearchGraphBuilder().build(nodes=(pinned,), edges=(secret_target_node_id,))


def test_research_graph_rejects_stale_source_pins() -> None:
    # Given: a stale external pin bypassing facade-level checks.
    stale = ResearchEvidenceNode(
        node_id="web.stale",
        source_kind="web_source_pin",
        source_pin=ResearchSourcePin(
            source_type="web_source_pin",
            source_url="https://docs.example.test/stale",
            source_commit="snapshot:old",
            trust_level="medium",
            freshness="stale",
            provenance_id="web.stale",
            summary="Stale source.",
            captured_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        ),
    )

    # When / Then: the graph builder refuses stale research evidence.
    with pytest.raises(ValueError, match="stale_source_blocked"):
        ResearchGraphBuilder().build(nodes=(stale,))


def _local_task_node() -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id="task.g005",
        source_kind="task_evidence_node",
        source_pin=ResearchSourcePin(
            source_type="task_evidence_node",
            source_url="https://tasks.platform.local/evidence/g005",
            source_commit="g005-evidence-node",
            trust_level="high",
            provenance_id="task.g005",
            summary="Task evidence node.",
        ),
    )
