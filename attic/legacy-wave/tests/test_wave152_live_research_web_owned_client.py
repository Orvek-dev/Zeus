from __future__ import annotations

import json

from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportRuntime
from zeus_agent.live_research_web_owned_client import (
    StaticWebResearchHttpFetcher,
    WebResearchHttpResponse,
    WebResearchOwnedClient,
)
from tests.test_wave141_live_research_external_transport import _research_policy


def test_web_research_owned_client_maps_search_response_to_receipt() -> None:
    fetcher = StaticWebResearchHttpFetcher(
        WebResearchHttpResponse(
            status_code=200,
            latency_ms=45,
            payload={
                "items": [
                    {
                        "title": "Zeus live platform notes",
                        "url": "https://docs.example.dev/zeus-live",
                    },
                ],
                "debug": "token=ghp_" + "wave152",
            },
        ),
    )
    policy = _research_policy().model_copy(update={"source_id": "web"})

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=WebResearchOwnedClient(fetcher=fetcher, endpoint="https://search.example.dev/query"),
        execution_ref="research-owned-client://wave152/web",
    )

    assert result.decision == "executed"
    assert result.research_owned_client is True
    assert result.external_transport_result is not None
    assert result.external_transport_result.source_id == "web"
    assert result.result_count == 1
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert "ghp_" + "wave152" not in json.dumps(result.to_payload())
    assert "q=parallel+coding+workflow" in fetcher.requests[0].url
    assert "limit=5" in fetcher.requests[0].url
    assert result.live_production_claimed is False


def test_web_research_owned_client_loopback_endpoint_does_not_satisfy_external_network() -> None:
    fetcher = StaticWebResearchHttpFetcher(
        WebResearchHttpResponse(
            status_code=200,
            latency_ms=11,
            payload={"items": [{"title": "local", "url": "http://127.0.0.1/page"}]},
        ),
    )
    policy = _research_policy().model_copy(update={"source_id": "web"})

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=WebResearchOwnedClient(fetcher=fetcher, endpoint="http://127.0.0.1/search"),
        execution_ref="research-owned-client://wave152/loopback",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_network_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_web_research_owned_client_blocks_wrong_source_before_fetch() -> None:
    fetcher = StaticWebResearchHttpFetcher(
        WebResearchHttpResponse(status_code=200, latency_ms=10, payload={"items": []}),
    )

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=WebResearchOwnedClient(fetcher=fetcher, endpoint="https://search.example.dev/query"),
        execution_ref="research-owned-client://wave152/wrong-source",
    )

    assert result.decision == "blocked"
    assert "research_owned_client_status_not_success" in result.blocked_reasons
    assert fetcher.requests == []
