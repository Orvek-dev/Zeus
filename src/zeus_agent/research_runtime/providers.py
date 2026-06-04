from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from zeus_agent.github_runtime import GitHubResearchFacade, GitHubSourcePin
from zeus_agent.research_runtime.models import ResearchEvidenceNode, ResearchSourcePin
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.web_runtime import WebResearchFacade, WebSourcePin


@dataclass(frozen=True)
class ResearchProviderQuery:
    objective_id: str
    query: str


@dataclass(frozen=True)
class ResearchProviderResponse:
    provider_id: str
    query: ResearchProviderQuery
    nodes: tuple[ResearchEvidenceNode, ...]
    planned_source_count: int
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False


@dataclass(frozen=True)
class FakeWebResearchProvider:
    provider_id: str
    sources: tuple[WebSourcePin, ...]

    def search(self, query: ResearchProviderQuery) -> ResearchProviderResponse:
        facade = WebResearchFacade()
        nodes = tuple(
            _web_node(source)
            for source in self.sources
            if facade.plan_source(source).decision == "planned"
        )
        return ResearchProviderResponse(
            provider_id=self.provider_id,
            query=_redact_query(query),
            nodes=nodes,
            planned_source_count=len(nodes),
        )


@dataclass(frozen=True)
class FakeGitHubResearchProvider:
    provider_id: str
    sources: tuple[GitHubSourcePin, ...]

    def search(self, query: ResearchProviderQuery) -> ResearchProviderResponse:
        facade = GitHubResearchFacade()
        nodes = tuple(
            _github_node(source)
            for source in self.sources
            if facade.plan_source(source).decision == "planned"
        )
        return ResearchProviderResponse(
            provider_id=self.provider_id,
            query=_redact_query(query),
            nodes=nodes,
            planned_source_count=len(nodes),
        )


def _redact_query(query: ResearchProviderQuery) -> ResearchProviderQuery:
    return ResearchProviderQuery(
        objective_id=redact_secret_spans(query.objective_id),
        query=redact_secret_spans(query.query),
    )


def _web_node(source: WebSourcePin) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=source.source_id,
        source_kind="web_source_pin",
        source_pin=ResearchSourcePin(
            source_type="web_source_pin",
            source_url=source.source_url,
            captured_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
            trust_level="medium",
            freshness=source.freshness,
            provenance_id=source.source_id,
            summary=source.summary,
        ),
    )


def _github_node(source: GitHubSourcePin) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=_github_node_id(source),
        source_kind="github_source_pin",
        source_pin=ResearchSourcePin(
            source_type="github_source_pin",
            source_url="https://github.com/{0}".format(source.repo),
            source_commit=source.ref,
            trust_level="medium",
            freshness=source.freshness,
            provenance_id=_github_node_id(source),
            summary=source.summary,
        ),
    )


def _github_node_id(source: GitHubSourcePin) -> str:
    if source.query_evidence_id is None:
        raise ValueError("github_query_evidence_missing")
    return source.query_evidence_id


__all__ = [
    "FakeGitHubResearchProvider",
    "FakeWebResearchProvider",
    "ResearchProviderQuery",
    "ResearchProviderResponse",
]
