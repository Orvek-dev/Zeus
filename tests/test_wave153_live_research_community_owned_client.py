from __future__ import annotations

import json

from zeus_agent.live_research_community_owned_client import (
    CommunityResearchHttpResponse,
    CommunityResearchOwnedClient,
    StaticCommunityResearchHttpFetcher,
)
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportRuntime
from tests.test_wave141_live_research_external_transport import _research_policy


def test_community_research_owned_client_maps_search_response_to_receipt() -> None:
    fetcher = StaticCommunityResearchHttpFetcher(
        CommunityResearchHttpResponse(
            status_code=200,
            latency_ms=49,
            payload={
                "items": [
                    {
                        "title": "Parallel agent workflow discussion",
                        "url": "https://community.example.dev/t/parallel-agent-workflow",
                    },
                ],
                "debug": "token=ghp_" + "wave153",
            },
        ),
    )
    policy = _research_policy().model_copy(update={"source_id": "community"})

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=CommunityResearchOwnedClient(fetcher=fetcher, endpoint="https://community.example.dev/search"),
        execution_ref="research-owned-client://wave153/community",
    )

    assert result.decision == "executed"
    assert result.research_owned_client is True
    assert result.external_transport_result is not None
    assert result.external_transport_result.source_id == "community"
    assert result.result_count == 1
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert "ghp_" + "wave153" not in json.dumps(result.to_payload())
    assert "q=parallel+coding+workflow" in fetcher.requests[0].url
    assert "limit=5" in fetcher.requests[0].url
    assert result.live_production_claimed is False


def test_community_research_owned_client_loopback_endpoint_does_not_satisfy_external_network() -> None:
    fetcher = StaticCommunityResearchHttpFetcher(
        CommunityResearchHttpResponse(
            status_code=200,
            latency_ms=13,
            payload={"items": [{"title": "local", "url": "http://127.0.0.1/thread"}]},
        ),
    )
    policy = _research_policy().model_copy(update={"source_id": "community"})

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=CommunityResearchOwnedClient(fetcher=fetcher, endpoint="http://127.0.0.1/search"),
        execution_ref="research-owned-client://wave153/loopback",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_network_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_community_research_owned_client_blocks_wrong_source_before_fetch() -> None:
    fetcher = StaticCommunityResearchHttpFetcher(
        CommunityResearchHttpResponse(status_code=200, latency_ms=10, payload={"items": []}),
    )

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=CommunityResearchOwnedClient(fetcher=fetcher, endpoint="https://community.example.dev/search"),
        execution_ref="research-owned-client://wave153/wrong-source",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_status_not_success" in result.blocked_reasons
    assert fetcher.requests == []
