from __future__ import annotations

import json

from zeus_agent.live_research_github_owned_client import (
    GitHubResearchOwnedClient,
    ResearchHttpResponse,
    StaticResearchHttpFetcher,
)
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportRuntime
from tests.test_wave141_live_research_external_transport import _research_policy


def test_github_research_owned_client_maps_search_response_to_receipt() -> None:
    fetcher = StaticResearchHttpFetcher(
        ResearchHttpResponse(
            status_code=200,
            latency_ms=39,
            payload={
                "items": [
                    {
                        "full_name": "Orvek-dev/Zeus",
                        "html_url": "https://github.com/Orvek-dev/Zeus",
                    },
                ],
                "debug": "token=ghp_" + "wave151",
            },
        ),
    )
    policy = _research_policy()

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=GitHubResearchOwnedClient(fetcher=fetcher),
        execution_ref="research-owned-client://wave151/github",
    )

    assert result.decision == "executed"
    assert result.research_owned_client is True
    assert result.external_transport_result is not None
    assert result.external_transport_result.decision == "executed"
    assert result.result_count == 1
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert "ghp_" + "wave151" not in json.dumps(result.to_payload())
    assert "q=parallel+coding+workflow" in fetcher.requests[0].url
    assert "per_page=5" in fetcher.requests[0].url
    assert result.live_production_claimed is False


def test_github_research_owned_client_loopback_endpoint_does_not_satisfy_external_network() -> None:
    fetcher = StaticResearchHttpFetcher(
        ResearchHttpResponse(
            status_code=200,
            latency_ms=12,
            payload={"items": [{"full_name": "local/fixture", "html_url": "http://127.0.0.1/repo"}]},
        ),
    )

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=GitHubResearchOwnedClient(
            fetcher=fetcher,
            endpoint="http://127.0.0.1/search/repositories",
        ),
        execution_ref="research-owned-client://wave151/loopback",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_network_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_github_research_owned_client_blocks_wrong_source_before_fetch() -> None:
    policy = _research_policy().model_copy(update={"source_id": "web"})
    fetcher = StaticResearchHttpFetcher(
        ResearchHttpResponse(status_code=200, latency_ms=10, payload={"items": []}),
    )

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=GitHubResearchOwnedClient(fetcher=fetcher),
        execution_ref="research-owned-client://wave151/wrong-source",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_status_not_success" in result.blocked_reasons
    assert fetcher.requests == []
