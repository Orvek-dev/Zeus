from __future__ import annotations

from zeus_agent.provider_owned_client_live_runtime.constants import DEFAULT_ALLOWED_HOST
from zeus_agent.provider_owned_client_live_runtime.constants import DEFAULT_ENDPOINT
from zeus_agent.provider_owned_client_live_runtime.constants import DEFAULT_MESSAGE
from zeus_agent.provider_owned_client_live_runtime.constants import DEFAULT_MODEL
from zeus_agent.provider_owned_client_live_runtime.constants import DEFAULT_SECRET_REF
from zeus_agent.provider_owned_client_live_runtime.contract import endpoint_allowlisted
from zeus_agent.provider_owned_client_live_runtime.contract import make_contract
from zeus_agent.provider_owned_client_live_runtime.models import ProviderOwnedClientLiveContract
from zeus_agent.provider_owned_client_live_runtime.pipeline import build_owned_client_smoke_contract

_SUPPORTED_SCENARIOS: frozenset[str] = frozenset(
    {
        "status",
        "blocked-missing-opt-in",
        "blocked-missing-secret",
        "owned-client-smoke",
    }
)


def build_provider_owned_client_live_contract(
    *,
    scenario: str = "status",
    endpoint: str = DEFAULT_ENDPOINT,
    allowed_host: str = DEFAULT_ALLOWED_HOST,
    secret_ref: str = DEFAULT_SECRET_REF,
    model_id: str = DEFAULT_MODEL,
    message: str = DEFAULT_MESSAGE,
) -> ProviderOwnedClientLiveContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return make_contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_provider_owned_client_live_scenario",),
        )
    if safe_scenario == "status":
        return make_contract(decision="report", scenario="status")
    if safe_scenario == "blocked-missing-opt-in":
        return _missing_opt_in(endpoint=endpoint, allowed_host=allowed_host)
    if safe_scenario == "blocked-missing-secret":
        return build_owned_client_smoke_contract(
            scenario="blocked-missing-secret",
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
        )
    return build_owned_client_smoke_contract(
        scenario="owned-client-smoke",
        endpoint=endpoint,
        allowed_host=allowed_host,
        secret_ref=secret_ref,
        model_id=model_id,
        message=message,
    )


def _missing_opt_in(*, endpoint: str, allowed_host: str) -> ProviderOwnedClientLiveContract:
    return make_contract(
        decision="blocked",
        scenario="blocked-missing-opt-in",
        blocked_reasons=("operator_live_opt_in_required",),
        endpoint_allowlisted=endpoint_allowlisted(endpoint, (allowed_host,)),
    )
