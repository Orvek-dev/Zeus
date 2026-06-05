from __future__ import annotations

import json

from zeus_agent.github_runtime import GitHubSourcePin
from zeus_agent.research_runtime.graph import ResearchGraphBuilder
from zeus_agent.research_runtime.models import ResearchEvidenceEdge, ResearchEvidenceNode, ResearchSourcePin
from zeus_agent.research_runtime.providers import (
    FakeGitHubResearchProvider,
    FakeWebResearchProvider,
    ResearchProviderQuery,
)
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.web_runtime import WebSourcePin


def build_research_brief(
    *,
    objective_id: str,
    query: str,
) -> dict[str, object]:
    safe_objective_id = redact_secret_spans(objective_id)
    safe_query = redact_secret_spans(query)
    research_query = ResearchProviderQuery(objective_id=safe_objective_id, query=safe_query)
    web_response = _web_provider().search(research_query)
    github_response = _github_provider().search(research_query)
    task_node = _task_node(safe_objective_id)
    graph = ResearchGraphBuilder().build(
        nodes=(*web_response.nodes, *github_response.nodes, task_node),
        edges=(
            ResearchEvidenceEdge(source_node_id="web.wave32.workflow", target_node_id="github.wave32.workflow", relation="supports"),
            ResearchEvidenceEdge(source_node_id="github.wave32.workflow", target_node_id="task.wave32.research", relation="verifies"),
        ),
    )
    payload = {
        "decision": "planned",
        "objective_id": safe_objective_id,
        "query": safe_query,
        "provider_count": 2,
        "graph_node_count": graph.node_count,
        "citation_edge_count": graph.edge_count,
        "external_claims_pinned": graph.external_claims_pinned,
        "provenance_ids": [node.node_id for node in graph.nodes],
        "recommendations": (
            "source_pinned_workflow_brief",
            "verify_live_sources_before_current_fact_claim",
            "keep_network_closed_until_live_research_lease",
        ),
        "network_opened": graph.network_opened or web_response.network_opened or github_response.network_opened,
        "handler_executed": graph.handler_executed or web_response.handler_executed or github_response.handler_executed,
        "client_constructed": web_response.client_constructed or github_response.client_constructed,
        "subprocess_started": web_response.subprocess_started or github_response.subprocess_started,
        "live_production_claimed": False,
    }
    payload["no_secret_echo"] = _no_secret_echo(payload) and graph.no_secret_echo
    return payload


def _web_provider() -> FakeWebResearchProvider:
    return FakeWebResearchProvider(
        provider_id="web.fake",
        sources=(
            WebSourcePin(
                source_id="web.wave32.workflow",
                source_url="https://docs.example.test/workflow",
                source_ref="snapshot:2026-06-04T00:00:00Z",
                source_pinned=True,
                freshness="fresh",
                summary="Pinned workflow source for orchestrated coding and research planning.",
            ),
        ),
    )


def _github_provider() -> FakeGitHubResearchProvider:
    return FakeGitHubResearchProvider(
        provider_id="github.fake",
        sources=(
            GitHubSourcePin(
                repo="orvek-dev/zeus",
                ref="wave32-research-fixture",
                query="workflow orchestration evidence",
                query_evidence_id="github.wave32.workflow",
                source_pinned=True,
                freshness="fresh",
                summary="Pinned repository evidence for workflow orchestration planning.",
            ),
        ),
    )


def _task_node(objective_id: str) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id="task.wave32.research",
        source_kind="task_evidence_node",
        source_pin=ResearchSourcePin(
            source_type="task_evidence_node",
            source_url="https://tasks.platform.local/evidence/wave32",
            source_commit="wave32-research-brief",
            trust_level="high",
            provenance_id="task.wave32.research",
            summary="Local task evidence for {0}.".format(objective_id),
        ),
    )


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    raw_markers = ("sk-wave", "token=sk", "ghp_", "github_pat_", "bearer ")
    return not any(marker in serialized for marker in raw_markers)


__all__ = ["build_research_brief"]
