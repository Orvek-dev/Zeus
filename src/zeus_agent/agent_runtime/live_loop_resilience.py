from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from zeus_agent.agent_runtime.live_loop_models import RetryPolicy
from zeus_agent.agent_runtime.live_loop_store import LiveAgentLoopPersistence
from zeus_agent.agent_runtime.live_loop_support import NOW
from zeus_agent.model_runtime.interfaces import (
    ProviderRuntimeKind,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
)
from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.runtime_lease import RuntimeLease

MAX_PROVIDER_ATTEMPTS: Final = 3


@dataclass(frozen=True)
class ProviderDispatchResult:
    response: ProviderRuntimeResponse
    attempts: int
    selected_request: ProviderRuntimeRequest
    selected_lease: RuntimeLease | None
    fallback_used: bool


def generate_provider_seed(
    *,
    provider_registry: ProviderRegistry,
    persistence: LiveAgentLoopPersistence,
    request: ProviderRuntimeRequest,
    lease: RuntimeLease | None,
    retry_policy: RetryPolicy | None,
    fallback_provider_kind: ProviderRuntimeKind | None,
    fallback_provider_lease: RuntimeLease | None,
) -> ProviderDispatchResult:
    max_attempts = _bounded_max_attempts(retry_policy)
    attempts = 1
    response = provider_registry.generate(request, lease, now=NOW)
    while response.decision == "blocked" and attempts < max_attempts:
        attempts += 1
        response = provider_registry.generate(request, lease, now=NOW)
    if response.decision != "blocked" or fallback_provider_kind is None:
        return ProviderDispatchResult(
            response=response,
            attempts=attempts,
            selected_request=request,
            selected_lease=lease,
            fallback_used=False,
        )

    attempts += 1
    fallback_request = request.model_copy(
        update={
            "provider_kind": fallback_provider_kind,
            "provider_id": "{0}.fallback".format(request.provider_id),
            "model_id": "{0}.wave15.local".format(fallback_provider_kind),
        },
    )
    fallback_response = provider_registry.generate(
        fallback_request,
        fallback_provider_lease or lease,
        now=NOW,
    )
    persistence.persist_policy_audit(
        reason=_fallback_audit_reason(fallback_response),
        message="{0}->{1}:{2}".format(
            request.provider_kind,
            fallback_provider_kind,
            _fallback_audit_decision(fallback_response),
        ),
    )
    return ProviderDispatchResult(
        response=fallback_response,
        attempts=attempts,
        selected_request=fallback_request,
        selected_lease=fallback_provider_lease or lease,
        fallback_used=True,
    )


def _bounded_max_attempts(retry_policy: RetryPolicy | None) -> int:
    if retry_policy is None:
        return 1
    return max(min(retry_policy.max_attempts, MAX_PROVIDER_ATTEMPTS), 1)


def retry_limit_reached(retry_policy: RetryPolicy | None, attempts: int) -> bool:
    return retry_policy is not None and attempts >= _bounded_max_attempts(retry_policy)


def _fallback_audit_reason(response: ProviderRuntimeResponse) -> str:
    if response.decision == "blocked":
        return "fallback_route_blocked"
    return "fallback_route_recorded"


def _fallback_audit_decision(response: ProviderRuntimeResponse) -> str:
    if response.decision == "blocked":
        return "blocked"
    return "selected"
