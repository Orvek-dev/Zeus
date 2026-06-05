from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

from zeus_agent.live_research_community_owned_client import (
    CommunityResearchOwnedClient,
    UrlLibCommunityResearchHttpFetcher,
)
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_github_owned_client import GitHubResearchOwnedClient, UrlLibResearchHttpFetcher
from zeus_agent.live_research_loopback_smoke_runtime.models import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientRequest
from zeus_agent.live_research_web_owned_client import UrlLibWebResearchHttpFetcher, WebResearchOwnedClient


class LiveResearchLoopbackSmokeRuntime:
    def execute(self, *, plan: LiveResearchExecutionPlanResult) -> LiveResearchLoopbackSmokeResult:
        reasons = _preflight_reasons(plan)
        if reasons:
            return _blocked(plan=plan, reasons=tuple(dict.fromkeys(reasons)))
        client = _client_for(plan.adapter_id, plan.endpoint)
        if client is None:
            return _blocked(plan=plan, reasons=("live_research_smoke_adapter_unknown",))
        receipt = client.search(_request_from_plan(plan))
        return LiveResearchLoopbackSmokeResult(
            decision="smoke_executed",
            execution_id=plan.execution_id,
            execution_ref=plan.execution_ref,
            adapter_id=plan.adapter_id,
            source_id=plan.source_id,
            endpoint=plan.endpoint,
            status_code=receipt.status_code,
            latency_ms=receipt.latency_ms,
            result_count=receipt.result_count,
            redacted_response=receipt.response_payload,
            cleanup_receipt=receipt.cleanup_receipt,
            client_constructed=True,
            research_invoked=True,
            network_opened=receipt.network_opened,
            non_loopback_network_opened=receipt.non_loopback_network_opened,
            external_evidence_ready=False,
            no_secret_echo=_no_secret_echo(receipt.response_payload),
        )


def _preflight_reasons(plan: LiveResearchExecutionPlanResult) -> list[str]:
    reasons: list[str] = []
    if plan.decision != "planned":
        reasons.append("live_research_execution_plan_not_planned")
    if plan.endpoint is None or not _is_loopback(plan.endpoint):
        reasons.append("live_research_smoke_endpoint_not_loopback")
    return reasons


def _client_for(adapter_id: Optional[str], endpoint: Optional[str]):
    if endpoint is None:
        return None
    if adapter_id == "github":
        return GitHubResearchOwnedClient(fetcher=UrlLibResearchHttpFetcher(), endpoint=endpoint)
    if adapter_id == "web":
        return WebResearchOwnedClient(fetcher=UrlLibWebResearchHttpFetcher(), endpoint=endpoint)
    if adapter_id == "community":
        return CommunityResearchOwnedClient(fetcher=UrlLibCommunityResearchHttpFetcher(), endpoint=endpoint)
    return None


def _request_from_plan(plan: LiveResearchExecutionPlanResult) -> LiveResearchOwnedClientRequest:
    return LiveResearchOwnedClientRequest(
        policy_id=plan.policy_id or "live-research-policy://unknown",
        source_id=plan.source_id or "unknown",
        query="loopback smoke",
        source_pin_ref=plan.source_pin_ref or "source-pin://unknown",
        max_results=plan.max_results or 1,
        rate_limit_per_minute=plan.rate_limit_per_minute or 1,
    )


def _is_loopback(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname
    return host in {"127.0.0.1", "localhost", "::1"} if host is not None else False


def _blocked(*, plan: LiveResearchExecutionPlanResult, reasons: tuple[str, ...]) -> LiveResearchLoopbackSmokeResult:
    return LiveResearchLoopbackSmokeResult(
        decision="blocked",
        execution_id=None,
        execution_ref=plan.execution_ref,
        adapter_id=plan.adapter_id,
        source_id=plan.source_id,
        endpoint=plan.endpoint,
        blocked_reasons=reasons,
    )


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("ghp_", "github_pat_", "sk-", "token=", "bearer ")
    return not any(marker in serialized for marker in markers)
