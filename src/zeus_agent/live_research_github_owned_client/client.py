from __future__ import annotations

from typing import Final
from urllib.parse import urlencode, urlparse

from pydantic import JsonValue

from zeus_agent.live_research_github_owned_client.models import ResearchHttpFetcher, ResearchHttpRequest
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientReceipt,
    LiveResearchOwnedClientRequest,
)
from zeus_agent.security.credentials import redact_secret_spans

_DEFAULT_ENDPOINT: Final = "https://api.github.com/search/repositories"
_CLEANUP_RECEIPT: Final = "research-owned-client-closed"


class GitHubResearchOwnedClient:
    def __init__(
        self,
        *,
        fetcher: ResearchHttpFetcher,
        endpoint: str = _DEFAULT_ENDPOINT,
        timeout_ms: int = 15000,
    ) -> None:
        self.fetcher = fetcher
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms

    def search(self, request: LiveResearchOwnedClientRequest) -> LiveResearchOwnedClientReceipt:
        if request.source_id != "github":
            return LiveResearchOwnedClientReceipt(
                status_code=400,
                latency_ms=0,
                source_pin_ref=request.source_pin_ref,
                result_count=0,
                response_payload={"items": [], "error": "github_source_required"},
                network_opened=False,
                non_loopback_network_opened=False,
                cleanup_receipt=_CLEANUP_RECEIPT,
            )
        response = self.fetcher.fetch(
            ResearchHttpRequest(
                url=_search_url(self.endpoint, request.query, request.max_results),
                timeout_ms=self.timeout_ms,
            ),
        )
        items = _items(response.payload, request.max_results)
        return LiveResearchOwnedClientReceipt(
            status_code=response.status_code,
            latency_ms=response.latency_ms,
            source_pin_ref=request.source_pin_ref,
            result_count=len(items),
            response_payload={"items": items},
            network_opened=True,
            non_loopback_network_opened=not _is_loopback_endpoint(self.endpoint),
            cleanup_receipt=_CLEANUP_RECEIPT,
        )


def _search_url(endpoint: str, query: str, max_results: int) -> str:
    separator = "&" if "?" in endpoint else "?"
    return "{0}{1}{2}".format(
        endpoint,
        separator,
        urlencode({"q": query, "per_page": max_results}),
    )


def _items(payload: dict[str, JsonValue], max_results: int) -> list[dict[str, JsonValue]]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, JsonValue]] = []
    for raw in raw_items[:max_results]:
        if not isinstance(raw, dict):
            continue
        title = raw.get("full_name")
        url = raw.get("html_url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        items.append(
            {
                "title": redact_secret_spans(title),
                "url": redact_secret_spans(url),
            },
        )
    return items


def _is_loopback_endpoint(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname
    if host is None:
        return False
    return host == "localhost" or host == "::1" or host.startswith("127.")
