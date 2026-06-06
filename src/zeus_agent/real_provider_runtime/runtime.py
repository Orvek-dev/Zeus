from __future__ import annotations

from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.model_runtime import ProviderProfile, provider_catalog
from zeus_agent.provider_live_optin_runtime import build_provider_live_optin_contract
from zeus_agent.provider_live_optin_runtime.contract import endpoint_allowlisted
from zeus_agent.provider_live_optin_runtime.contract import endpoint_host
from zeus_agent.real_provider_runtime.models import RealProviderContract
from zeus_agent.real_provider_runtime.models import RealProviderDecision
from zeus_agent.real_provider_runtime.models import RealProviderProfile
from zeus_agent.real_provider_runtime.models import RealProviderScenario

_TARGET_VERSION: Final = "v1.1.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.1.0.real_provider_runtime"
_DEFAULT_ENDPOINT: Final = "https://api.openai.local/v1/chat/completions"
_DEFAULT_ALLOWED_HOST: Final = "api.openai.local"
_DEFAULT_SECRET_REF: Final = "env://ZEUS_V110_PROVIDER_KEY"
_DEFAULT_MODEL: Final = "gpt-v110-provider"
_DEFAULT_MESSAGE: Final = "summarize Zeus real provider runtime"
_MESSAGE_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "-----begin",
)
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "blocked-missing-opt-in",
        "blocked-unallowlisted",
        "blocked-budget",
        "local-deterministic-smoke",
        "external-receipt-smoke",
    },
)


def build_real_provider_contract(
    *,
    scenario: str = "status",
    endpoint: str = _DEFAULT_ENDPOINT,
    allowed_host: str = _DEFAULT_ALLOWED_HOST,
    secret_ref: str = _DEFAULT_SECRET_REF,
    model_id: str = _DEFAULT_MODEL,
    message: str = _DEFAULT_MESSAGE,
    budget_limit: int = 8,
    budget_requested: int = 2,
    timeout_ms: int = 1500,
) -> RealProviderContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_provider_scenario",),
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if parsed_scenario == "status":
        return _contract(
            decision="report",
            scenario="status",
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
    if parsed_scenario == "blocked-missing-opt-in":
        return _blocked_missing_optin(
            endpoint=endpoint,
            allowed_host=allowed_host,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
    if parsed_scenario == "blocked-unallowlisted":
        return _contract(
            decision="blocked",
            scenario="blocked-unallowlisted",
            blocked_reasons=("remote_target_allowlist_required", "remote_target_not_allowlisted"),
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
            operator_live_opted_in=True,
            endpoint_allowlisted=False,
        )
    if parsed_scenario == "blocked-budget":
        return _blocked_budget(
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
    if parsed_scenario == "local-deterministic-smoke":
        return _local_smoke(
            message=message,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
    return _external_receipt_smoke(
        endpoint=endpoint,
        allowed_host=allowed_host,
        secret_ref=secret_ref,
        model_id=model_id,
        message=message,
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
    )


def _parse_scenario(value: str) -> RealProviderScenario:
    if value == "status":
        return "status"
    if value == "blocked-missing-opt-in":
        return "blocked-missing-opt-in"
    if value == "blocked-unallowlisted":
        return "blocked-unallowlisted"
    if value == "blocked-budget":
        return "blocked-budget"
    if value == "local-deterministic-smoke":
        return "local-deterministic-smoke"
    if value == "external-receipt-smoke":
        return "external-receipt-smoke"
    return "status"


def _blocked_missing_optin(
    *,
    endpoint: str,
    allowed_host: str,
    budget_limit: int,
    budget_requested: int,
    timeout_ms: int,
) -> RealProviderContract:
    policy_bound = _receipt_policy_bound(endpoint=endpoint, allowed_host=allowed_host)
    return _contract(
        decision="blocked",
        scenario="blocked-missing-opt-in",
        blocked_reasons=("operator_live_opt_in_required",),
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
        endpoint_allowlisted=policy_bound,
    )


def _blocked_budget(*, budget_limit: int, budget_requested: int, timeout_ms: int) -> RealProviderContract:
    return _contract(
        decision="blocked",
        scenario="blocked-budget",
        blocked_reasons=_budget_block_reasons(
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        )
        or ("provider_budget_exceeded",),
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
        budget_approved=False,
    )


def _local_smoke(*, message: str, budget_limit: int, budget_requested: int, timeout_ms: int) -> RealProviderContract:
    budget_reasons = _budget_block_reasons(
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
    )
    if budget_reasons:
        return _contract(
            decision="blocked",
            scenario="local-deterministic-smoke",
            blocked_reasons=budget_reasons,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
            budget_approved=False,
        )
    if _message_has_secret_marker(message):
        return _contract(
            decision="blocked",
            scenario="local-deterministic-smoke",
            blocked_reasons=("secret_like_message_blocked",),
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
            budget_approved=False,
        )
    return _contract(
        decision="report",
        scenario="local-deterministic-smoke",
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
        budget_approved=True,
        local_provider_ready=True,
        real_provider_runtime_ready=True,
        provider_invoked=True,
        local_smoke={
            "provider_id": "local-deterministic",
            "model_id": "local.zeus",
            "response": {
                "content": "local deterministic provider: {0}".format(message),
                "usage": {"input_tokens": len(message.split()), "output_tokens": 4, "budget_units": budget_requested},
            },
            "audit": {"decision": "audit_ready", "network_opened": False, "credential_material_accessed": False},
        },
    )


def _external_receipt_smoke(
    *,
    endpoint: str,
    allowed_host: str,
    secret_ref: str,
    model_id: str,
    message: str,
    budget_limit: int,
    budget_requested: int,
    timeout_ms: int,
) -> RealProviderContract:
    budget_reasons = _budget_block_reasons(
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
    )
    if budget_reasons:
        return _blocked_budget(budget_limit=budget_limit, budget_requested=budget_requested, timeout_ms=timeout_ms)
    policy_reasons = _receipt_policy_block_reasons(endpoint=endpoint, allowed_host=allowed_host)
    if policy_reasons:
        return _contract(
            decision="blocked",
            scenario="external-receipt-smoke",
            blocked_reasons=policy_reasons,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
            budget_approved=True,
            endpoint_allowlisted=False,
        )
    if _message_has_secret_marker(message):
        return _contract(
            decision="blocked",
            scenario="external-receipt-smoke",
            blocked_reasons=("secret_like_message_blocked",),
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
            budget_approved=True,
            operator_live_opted_in=False,
            endpoint_allowlisted=True,
        )
    external = build_provider_live_optin_contract(
        scenario="external-receipt-smoke",
        endpoint=endpoint,
        allowed_host=_DEFAULT_ALLOWED_HOST,
        secret_ref=secret_ref,
        model_id=model_id,
        message=message,
    )
    payload = external.to_payload()
    ready = external.decision == "report" and bool(payload["provider_live_optin_ready"])
    return _contract(
        decision="report" if ready else "blocked",
        scenario="external-receipt-smoke",
        blocked_reasons=() if ready else tuple(str(reason) for reason in payload["blocked_reasons"]),
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
        budget_approved=True,
        operator_live_opted_in=bool(payload["operator_live_opted_in"]),
        endpoint_allowlisted=bool(payload["endpoint_allowlisted"]),
        secret_material_available=bool(payload["secret_material_available"]),
        external_provider_ready=ready,
        real_provider_runtime_ready=ready,
        external_smoke=payload,
        network_opened=bool(payload["network_opened"]),
        non_loopback_network_opened=bool(payload["non_loopback_network_opened"]),
        controlled_external_side_effects=bool(payload["controlled_external_side_effects"]),
        provider_invoked=bool(payload["provider_invoked"]),
        handler_executed=bool(payload["handler_executed"]),
        credential_material_accessed=bool(payload["credential_material_accessed"]),
    )


def _contract(
    *,
    decision: RealProviderDecision,
    scenario: RealProviderScenario,
    blocked_reasons: tuple[str, ...] = (),
    budget_limit: int,
    budget_requested: int,
    timeout_ms: int,
    budget_approved: Optional[bool] = None,
    operator_live_opted_in: bool = False,
    endpoint_allowlisted: bool = False,
    secret_material_available: bool = False,
    local_provider_ready: bool = False,
    external_provider_ready: bool = False,
    real_provider_runtime_ready: bool = False,
    local_smoke: Optional[dict[str, JsonValue]] = None,
    external_smoke: Optional[dict[str, JsonValue]] = None,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    controlled_external_side_effects: bool = False,
    provider_invoked: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
) -> RealProviderContract:
    profiles = _profiles()
    approved = _budget_approved(
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
    ) if budget_approved is None else budget_approved
    result = RealProviderContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="real_provider_runtime",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        provider_profile_count=len(profiles),
        provider_profiles=profiles,
        local_llm_profile_available=any(profile.runtime_kind == "local_llm" for profile in profiles),
        openai_compatible_profile_available=any(profile.api_mode == "openai_compatible" for profile in profiles),
        governed_external_provider_available=any(profile.credential_scope is not None for profile in profiles),
        real_provider_runtime_ready=real_provider_runtime_ready,
        local_provider_ready=local_provider_ready,
        external_provider_ready=external_provider_ready,
        production_ready=False,
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        budget_approved=approved,
        timeout_ms=timeout_ms,
        operator_live_opted_in=operator_live_opted_in,
        endpoint_allowlisted=endpoint_allowlisted,
        secret_material_available=secret_material_available,
        local_smoke=local_smoke,
        external_smoke=external_smoke,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=controlled_external_side_effects,
        provider_invoked=provider_invoked,
        handler_executed=handler_executed,
        credential_material_accessed=credential_material_accessed,
        raw_secret_returned=False,
        external_delivery_opened=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _budget_approved(*, budget_limit: int, budget_requested: int, timeout_ms: int) -> bool:
    return not _budget_block_reasons(
        budget_limit=budget_limit,
        budget_requested=budget_requested,
        timeout_ms=timeout_ms,
    )


def _budget_block_reasons(*, budget_limit: int, budget_requested: int, timeout_ms: int) -> tuple[str, ...]:
    reasons: list[str] = []
    if budget_limit <= 0 or budget_requested <= 0:
        reasons.append("provider_budget_invalid")
    elif budget_requested > budget_limit:
        reasons.append("provider_budget_exceeded")
    if timeout_ms <= 0:
        reasons.append("provider_timeout_invalid")
    return tuple(reasons)


def _message_has_secret_marker(message: str) -> bool:
    normalized = message.lower()
    return any(marker in normalized for marker in _MESSAGE_SECRET_MARKERS)


def _receipt_policy_bound(*, endpoint: str, allowed_host: str) -> bool:
    return not _receipt_policy_block_reasons(endpoint=endpoint, allowed_host=allowed_host)


def _receipt_policy_block_reasons(*, endpoint: str, allowed_host: str) -> tuple[str, ...]:
    host = endpoint_host(endpoint)
    if host is None:
        return ("malformed_provider_endpoint",)
    if endpoint != _DEFAULT_ENDPOINT or host != _DEFAULT_ALLOWED_HOST or allowed_host != _DEFAULT_ALLOWED_HOST:
        return ("provider_endpoint_policy_required",)
    if not endpoint_allowlisted(endpoint, (_DEFAULT_ALLOWED_HOST,)):
        return ("remote_target_not_allowlisted",)
    return ()


def _profiles() -> tuple[RealProviderProfile, ...]:
    return tuple(_profile_payload(profile) for profile in provider_catalog())


def _profile_payload(profile: ProviderProfile) -> RealProviderProfile:
    return RealProviderProfile(
        provider_id=profile.provider_id,
        display_name=profile.display_name,
        api_mode=profile.api_mode,
        default_model=profile.default_model,
        runtime_kind=profile.runtime_kind,
        network_host=profile.network_host,
        credential_scope=profile.credential_scope,
        local_first=profile.local_first,
        tool_calling=profile.tool_calling,
        streaming=profile.streaming,
        structured_output=profile.structured_output,
        vision=profile.vision,
        embeddings=profile.embeddings,
        live_beta=profile.live_beta,
    )
