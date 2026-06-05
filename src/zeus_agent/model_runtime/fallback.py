from __future__ import annotations

from dataclasses import dataclass

from zeus_agent.model_runtime.provider_catalog import ProviderProfile, get_provider_profile
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans


@dataclass(frozen=True)
class ProviderFallbackDecision:
    primary_provider_id: str
    fallback_provider_id: str
    decision: str
    reason: str | None
    credential_scope_allowed: bool
    network_host_allowed: bool
    budget_required: int
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "primary_provider_id": self.primary_provider_id,
            "fallback_provider_id": self.fallback_provider_id,
            "decision": self.decision,
            "reason": self.reason,
            "credential_scope_allowed": self.credential_scope_allowed,
            "network_host_allowed": self.network_host_allowed,
            "budget_required": self.budget_required,
            "live_production_claimed": self.live_production_claimed,
        }


def evaluate_provider_fallback(
    *,
    primary_provider_id: str,
    fallback_provider_id: str,
    lease: RuntimeLease,
    budget_required: int = 1,
) -> ProviderFallbackDecision:
    primary = get_provider_profile(primary_provider_id)
    fallback = get_provider_profile(fallback_provider_id)
    credential_allowed = _credential_allowed(fallback, lease)
    network_allowed = _network_allowed(fallback, lease)
    if budget_required > lease.budget_limit:
        return _blocked(primary, fallback, "budget_exceeded", credential_allowed, network_allowed, budget_required)
    if fallback.credential_scope is not None and not credential_allowed:
        return _blocked(primary, fallback, "fallback_credential_scope_not_leased", credential_allowed, network_allowed, budget_required)
    if fallback.network_host is not None and not network_allowed:
        return _blocked(primary, fallback, "fallback_network_host_not_leased", credential_allowed, network_allowed, budget_required)
    if primary.local_first and not fallback.local_first and not lease.live_transport_allowed:
        return _blocked(primary, fallback, "local_to_external_fallback_requires_live_transport", credential_allowed, network_allowed, budget_required)
    return ProviderFallbackDecision(
        primary_provider_id=primary.provider_id,
        fallback_provider_id=fallback.provider_id,
        decision="allowed",
        reason=None,
        credential_scope_allowed=credential_allowed,
        network_host_allowed=network_allowed,
        budget_required=budget_required,
    )


def provider_budget_payload(
    *,
    provider_id: str,
    lease: RuntimeLease,
    budget_required: int,
) -> dict[str, object]:
    provider = get_provider_profile(provider_id)
    allowed = budget_required <= lease.budget_limit
    return {
        "provider_id": redact_secret_spans(provider.provider_id),
        "budget_required": budget_required,
        "budget_limit": lease.budget_limit,
        "decision": "allowed" if allowed else "blocked",
        "reason": None if allowed else "budget_exceeded",
        "live_production_claimed": False,
    }


def _credential_allowed(provider: ProviderProfile, lease: RuntimeLease) -> bool:
    if provider.credential_scope is None:
        return True
    return provider.credential_scope in set(lease.credential_scopes)


def _network_allowed(provider: ProviderProfile, lease: RuntimeLease) -> bool:
    if provider.network_host is None:
        return True
    return provider.network_host in set(lease.network_hosts)


def _blocked(
    primary: ProviderProfile,
    fallback: ProviderProfile,
    reason: str,
    credential_allowed: bool,
    network_allowed: bool,
    budget_required: int,
) -> ProviderFallbackDecision:
    return ProviderFallbackDecision(
        primary_provider_id=primary.provider_id,
        fallback_provider_id=fallback.provider_id,
        decision="blocked",
        reason=reason,
        credential_scope_allowed=credential_allowed,
        network_host_allowed=network_allowed,
        budget_required=budget_required,
    )


__all__ = [
    "ProviderFallbackDecision",
    "evaluate_provider_fallback",
    "provider_budget_payload",
]
