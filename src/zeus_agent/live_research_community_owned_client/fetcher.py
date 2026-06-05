from __future__ import annotations

from zeus_agent.live_research_community_owned_client.models import (
    CommunityResearchHttpRequest,
    CommunityResearchHttpResponse,
)
from zeus_agent.live_research_http_fetcher_runtime import get_research_json


class UrlLibCommunityResearchHttpFetcher:
    def fetch(self, request: CommunityResearchHttpRequest) -> CommunityResearchHttpResponse:
        result = get_research_json(url=request.url, timeout_ms=request.timeout_ms)
        return CommunityResearchHttpResponse(
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            payload=result.payload,
        )
