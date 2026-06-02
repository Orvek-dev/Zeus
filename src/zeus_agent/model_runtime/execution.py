from __future__ import annotations

from typing import Callable, Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import AuthorityContext
from zeus_agent.model_runtime.providers import (
    ProviderKind,
    ProviderRouteRequest,
    default_provider_router,
)
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError
from zeus_agent.transport_runtime import (
    TransportExecutionGate,
    TransportExecutionGateRequest,
    TransportKind,
    TransportRegistry,
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class ProviderExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderKind
    prompt: str
    required_tool_calling: bool = False
    required_json_mode: bool = False
    required_streaming: bool = False
    local_private: Optional[bool] = None
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None

    @field_validator("prompt")
    @classmethod
    def _validate_prompt(cls, value: str) -> str:
        return _require_non_empty(value, "prompt")

    @field_validator("credential_scope", "network_host")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class ProviderExecutionRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["selected", "blocked"]
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    reason: Optional[str] = None
    network_allowed: bool


class ProviderExecutionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderKind
    provider_id: str
    model_id: str
    local_private: bool
    transport: Literal["dry_run"] = "dry_run"
    network_allowed: bool
    network_host: Optional[str] = None
    credential_scope_label: Optional[str] = None
    raw_env_reads: bool = False
    credential_material_accessed: bool = False
    side_effects: bool = False


class ProviderExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["selected", "blocked"]
    route: ProviderExecutionRoute
    envelope: Optional[ProviderExecutionEnvelope] = None
    reason: Optional[str] = None
    redacted_input: Optional[str] = None


_PROVIDER_CAPABILITY_IDS: Final[dict[ProviderKind, str]] = {
    "fake": "provider.fake.generate",
    "local": "provider.local.generate",
    "external": "provider.external.generate",
}


class ProviderExecutionRuntime:
    def __init__(self, transport_registry: Optional[TransportRegistry] = None) -> None:
        self._transport_gate = (
            TransportExecutionGate(transport_registry)
            if transport_registry is not None
            else None
        )

    def prepare(
        self,
        request: ProviderExecutionRequest,
        authority: AuthorityContext,
    ) -> ProviderExecutionResult:
        credential_result = _credential_scope_label(request.credential_scope)
        if credential_result.decision == "blocked":
            return _blocked_result(
                reason=credential_result.reason or "credential_scope_invalid",
                network_allowed=False,
                redacted_input=credential_result.redacted_input,
            )

        capability_id = _provider_capability_id(request.provider)
        authority_decision = _authority_decision(
            request=request,
            authority=authority,
            capability_id=capability_id,
            credential_scope_label=credential_result.label,
        )
        if authority_decision.decision == "blocked":
            return _blocked_result(
                reason=authority_decision.reason,
                network_allowed=False,
            )

        if self._transport_gate is not None:
            gate = self._transport_gate.evaluate(
                TransportExecutionGateRequest(
                    capability_id=capability_id,
                    transport_kind=TransportKind.provider,
                    credential_scope=credential_result.label,
                ),
                authority,
            )
            if gate.decision == "blocked":
                return _blocked_result(
                    reason=gate.reason,
                    network_allowed=False,
                    redacted_input=gate.redacted_input,
                )

        route = default_provider_router().route(
            ProviderRouteRequest(
                provider=request.provider,
                required_tool_calling=request.required_tool_calling,
                required_json_mode=request.required_json_mode,
                required_streaming=request.required_streaming,
                local_private=request.local_private,
                credential_scope=credential_result.label,
                network_allowed=_network_allowed(request.provider, request.network_host),
            )
        )
        if route.decision == "blocked":
            return _blocked_result(
                reason=route.reason or "provider_route_blocked",
                network_allowed=False,
                provider_id=route.provider_id,
                model_id=route.model_id,
            )

        return ProviderExecutionResult(
            decision="selected",
            route=ProviderExecutionRoute(
                decision="selected",
                provider_id=route.provider_id,
                model_id=route.model_id,
                network_allowed=_network_allowed(request.provider, request.network_host),
            ),
            envelope=ProviderExecutionEnvelope(
                provider=request.provider,
                provider_id=_require_non_empty(route.provider_id or "", "provider_id"),
                model_id=_require_non_empty(route.model_id or "", "model_id"),
                local_private=bool(route.local_private),
                network_allowed=_network_allowed(request.provider, request.network_host),
                network_host=request.network_host,
                credential_scope_label=credential_result.label,
            ),
        )


class _CredentialScopeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked"]
    label: Optional[str] = None
    reason: Optional[str] = None
    redacted_input: Optional[str] = None


def _credential_scope_label(raw_value: Optional[str]) -> _CredentialScopeResult:
    if raw_value is None:
        return _CredentialScopeResult(decision="allowed")
    try:
        scope = CredentialScope.parse(raw_value)
    except CredentialScopeUnsafeError as exc:
        return _CredentialScopeResult(
            decision="blocked",
            reason=exc.payload["reason"],
            redacted_input=exc.payload["redacted"],
        )
    except ValueError as exc:
        return _CredentialScopeResult(decision="blocked", reason=str(exc))
    return _CredentialScopeResult(decision="allowed", label=scope.label)


def _provider_capability_id(provider: ProviderKind) -> str:
    return _PROVIDER_CAPABILITY_IDS[provider]


def _authority_decision(
    *,
    request: ProviderExecutionRequest,
    authority: AuthorityContext,
    capability_id: str,
    credential_scope_label: Optional[str],
) -> object:
    decisions: dict[ProviderKind, Callable[[], object]] = {
        "fake": lambda: authority.allows(capability_id),
        "local": lambda: authority.allows(capability_id),
        "external": lambda: authority.allows(
            capability_id,
            network_host=request.network_host,
            credential_scope=credential_scope_label,
        )
        if request.network_host is not None
        else authority.allows(
            capability_id,
            credential_scope=credential_scope_label,
        ),
    }
    return decisions[request.provider]()


def _network_allowed(provider: ProviderKind, network_host: Optional[str]) -> bool:
    return provider == "external" and network_host is not None


def _blocked_result(
    *,
    reason: str,
    network_allowed: bool,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
    redacted_input: Optional[str] = None,
) -> ProviderExecutionResult:
    return ProviderExecutionResult(
        decision="blocked",
        reason=reason,
        redacted_input=redacted_input,
        route=ProviderExecutionRoute(
            decision="blocked",
            provider_id=provider_id,
            model_id=model_id,
            reason=reason,
            network_allowed=network_allowed,
        ),
    )
