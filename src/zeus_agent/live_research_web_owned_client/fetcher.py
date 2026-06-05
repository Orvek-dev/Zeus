from __future__ import annotations

from zeus_agent.live_research_http_fetcher_runtime import get_research_json
from zeus_agent.live_research_web_owned_client.models import WebResearchHttpRequest, WebResearchHttpResponse


class UrlLibWebResearchHttpFetcher:
    def fetch(self, request: WebResearchHttpRequest) -> WebResearchHttpResponse:
        result = get_research_json(url=request.url, timeout_ms=request.timeout_ms)
        return WebResearchHttpResponse(
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            payload=result.payload,
        )
