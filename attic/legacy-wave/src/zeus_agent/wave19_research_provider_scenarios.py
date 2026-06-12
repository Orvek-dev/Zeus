from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Union

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
from zeus_agent.web_runtime import WebSourcePin

Wave19PayloadValue = Union[bool, int, str, list[str]]
Wave19Payload = dict[str, Wave19PayloadValue]


def wave19_research_provider_payload(*, scenario: str = "pinned-fake") -> Wave19Payload:
    if scenario != "pinned-fake":
        raise ValueError("scenario must be pinned-fake")
    query = ResearchProviderQuery(objective_id="g005", query="research provider")
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
    web_response = web.search(query)
    github_response = github.search(query)
    graph = ResearchGraphBuilder().build(
        nodes=(*web_response.nodes, *github_response.nodes, _task_node()),
        edges=_happy_edges(),
    )
    provenance_ids = [node.node_id for node in graph.nodes]
    serialized = json.dumps(graph.model_dump(mode="json"), sort_keys=True)
    return {
        "scenario_id": "C001",
        "web_provider_created": True,
        "github_provider_created": True,
        "fake_web_provider_called": True,
        "fake_github_provider_called": True,
        "web_source_planned": web_response.planned_source_count == 1,
        "github_source_planned": github_response.planned_source_count == 1,
        "source_pins_created": web_response.planned_source_count + github_response.planned_source_count,
        "fresh_sources_accepted": graph.external_claims_pinned,
        "graph_created": True,
        "graph_node_count": graph.node_count,
        "citation_edge_count": graph.edge_count,
        "provenance_ids": provenance_ids,
        "external_claims_pinned": graph.external_claims_pinned,
        "stale_source_blocked": False,
        "handler_executed": graph.handler_executed,
        "network_opened": graph.network_opened,
        "client_constructed": web_response.client_constructed or github_response.client_constructed,
        "subprocess_started": web_response.subprocess_started or github_response.subprocess_started,
        "real_web_adapter_used": False,
        "real_github_adapter_used": False,
        "no_secret_echo": graph.no_secret_echo and "sk-" not in serialized,
        "live_production_claimed": False,
    }


def wave19_research_provider_blocks_payload(*, raw_secret: str) -> Wave19Payload:
    results = {
        "unpinned_web_source": _web_status(WebSourcePin(**_web_source(source_pinned=False))),
        "missing_web_source_ref": _web_status(WebSourcePin(**_web_source(source_ref=None))),
        "stale_web_source": _web_status(WebSourcePin(**_web_source(freshness="stale"))),
        "secret_web_summary": _web_status(WebSourcePin(**_web_source(summary=raw_secret))),
        "github_missing_ref": _github_status(GitHubSourcePin(**_github_source(ref=None))),
        "github_missing_query_evidence": _github_status(
            GitHubSourcePin(**_github_source(query_evidence_id=None)),
        ),
        "unpinned_github_source": _github_status(
            GitHubSourcePin(**_github_source(source_pinned=False)),
        ),
        "stale_github_source": _github_status(GitHubSourcePin(**_github_source(freshness="stale"))),
        "secret_github_query": _github_status(GitHubSourcePin(**_github_source(query=raw_secret))),
        "stale_graph_source": _build_status((_stale_graph_node(),), ()),
        "unpinned_graph_external_claim": _build_status(
            (ResearchEvidenceNode(node_id="task.unpinned", source_kind="task_evidence_node"),),
            (),
        ),
        "duplicate_graph_node": _build_status((_task_node(), _task_node()), ()),
        "missing_edge_target": _build_status(
            (_task_node(),),
            (ResearchEvidenceEdge(source_node_id="task.g005", target_node_id="missing", relation="cites"),),
        ),
    }
    payload: Wave19Payload = {
        "scenario_id": "C002",
        **results,
        "blocked_handler_executed": False,
        "blocked_network_opened": False,
        "client_constructed": False,
        "subprocess_started": False,
        "real_web_adapter_used": False,
        "real_github_adapter_used": False,
        "raw_secret_present": False,
        "no_secret_echo": True,
        "live_production_claimed": False,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return {
        **payload,
        "raw_secret_present": raw_secret in serialized,
        "no_secret_echo": raw_secret not in serialized,
    }


def _web_status(source: WebSourcePin) -> str:
    query = ResearchProviderQuery(objective_id="g005", query="blocked web source")
    response = FakeWebResearchProvider(provider_id="web.fake", sources=(source,)).search(query)
    return "blocked" if response.planned_source_count == 0 else "allowed"


def _github_status(source: GitHubSourcePin) -> str:
    query = ResearchProviderQuery(objective_id="g005", query="blocked github source")
    response = FakeGitHubResearchProvider(provider_id="github.fake", sources=(source,)).search(query)
    return "blocked" if response.planned_source_count == 0 else "allowed"


def _build_status(
    nodes: tuple[ResearchEvidenceNode, ...],
    edges: tuple[ResearchEvidenceEdge, ...],
) -> str:
    try:
        ResearchGraphBuilder().build(nodes=nodes, edges=edges)
    except ValueError:
        return "blocked"
    return "allowed"


def _web_source(
    *,
    source_ref: str | None = "snapshot:2026-06-03T00:00:00Z",
    source_pinned: bool = True,
    freshness: str = "fresh",
    summary: str = "Pinned web source.",
) -> dict[str, str | bool | None]:
    return {
        "source_id": "web.docs.zeus",
        "source_url": "https://docs.example.test/zeus",
        "source_ref": source_ref,
        "source_pinned": source_pinned,
        "freshness": freshness,
        "summary": summary,
    }


def _github_source(
    *,
    ref: str | None = "9f2d4a1",
    query_evidence_id: str | None = "evidence.github.query.001",
    source_pinned: bool = True,
    freshness: str = "fresh",
    query: str = "is:issue label:G005 research provider",
) -> dict[str, str | bool | None]:
    return {
        "repo": "owner/zeus",
        "ref": ref,
        "query": query,
        "query_evidence_id": query_evidence_id,
        "source_pinned": source_pinned,
        "freshness": freshness,
        "summary": "Pinned issue query summary.",
    }


def _happy_edges() -> tuple[ResearchEvidenceEdge, ...]:
    return (
        ResearchEvidenceEdge(
            source_node_id="web.docs.zeus",
            target_node_id="evidence.github.query.001",
            relation="supports",
        ),
        ResearchEvidenceEdge(
            source_node_id="evidence.github.query.001",
            target_node_id="task.g005",
            relation="verifies",
        ),
        ResearchEvidenceEdge(
            source_node_id="task.g005",
            target_node_id="web.docs.zeus",
            relation="cites",
        ),
    )


def _task_node() -> ResearchEvidenceNode:
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


def _stale_graph_node() -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
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
