from __future__ import annotations

from zeus_agent.live_research_github_owned_client.models import ResearchHttpRequest, ResearchHttpResponse
from zeus_agent.live_research_http_fetcher_runtime import get_research_json


class UrlLibResearchHttpFetcher:
    def fetch(self, request: ResearchHttpRequest) -> ResearchHttpResponse:
        result = get_research_json(url=request.url, timeout_ms=request.timeout_ms)
        return ResearchHttpResponse(
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            payload=result.payload,
        )
