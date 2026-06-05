from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.model_runtime import ProviderMessage, ProviderRuntimeRequest
from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderExecutionDecision = Literal["selected", "blocked"]
LiveProviderKind = Literal["fake", "local_llm", "openai_compatible", "anthropic_metadata"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_LOCAL_PROVIDER_CAPABILITIES: Final = {
    "fake": "provider.fake.generate",
    "local_llm": "provider.local.generate",
}
_PROVIDER_IDS: Final = {
    "fake": "fake.live",
    "local_llm": "local.live",
}
_MODEL_IDS: Final = {
    "fake": "fake.live.model",
    "local_llm": "local.live.model",
}
_NOW: Final = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveProviderExecutionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderExecutionDecision
    provider_kind: Optional[LiveProviderKind]
    provider_decision: Optional[str] = None
    provider_invoked: bool = False
    content: Optional[str] = None
    response_id: Optional[str] = None
    provider_response: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    local_only: bool = True
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderExecutionRuntime:
    def __init__(self, provider_registry: Optional[ProviderRegistry] = None) -> None:
        self.provider_registry = provider_registry or ProviderRegistry()

    def generate(
        self,
        *,
        readiness: Optional[LiveExecutionReadinessResult],
        provider_kind: str,
        message: str,
    ) -> LiveProviderExecutionResult:
        safe_provider_kind = provider_kind.strip()
        safe_message = redact_secret_spans(message.strip())
        reasons = list(_readiness_reasons(readiness))
        if safe_provider_kind not in _LOCAL_PROVIDER_CAPABILITIES:
            reasons.append("external_provider_execution_not_enabled")
        if safe_message == "":
            reasons.append("message_required")
        if reasons:
            return _result(
                decision="blocked",
                provider_kind=safe_provider_kind,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )

        try:
            request = ProviderRuntimeRequest(
                provider_kind=safe_provider_kind,
                provider_id=_PROVIDER_IDS[safe_provider_kind],
                model_id=_MODEL_IDS[safe_provider_kind],
                messages=(ProviderMessage(role="user", content=safe_message),),
                evidence_target="mneme.wave86.live_provider_execution",
            )
        except (KeyError, ValidationError):
            return _result(
                decision="blocked",
                provider_kind=safe_provider_kind,
                blocked_reasons=("malformed_provider_request",),
            )
        response = self.provider_registry.generate(
            request,
            _lease(safe_provider_kind),
            now=_NOW,
        )
        return _result(
            decision="selected" if response.decision == "selected" else "blocked",
            provider_kind=safe_provider_kind,
            provider_decision=response.decision,
            provider_invoked=response.decision == "selected",
            content=response.content,
            response_id=response.response_id,
            provider_response=response.model_dump(mode="json"),
            blocked_reasons=() if response.decision == "selected" else (response.reason or "provider_blocked",),
            network_opened=response.network_opened,
            handler_executed=response.handler_executed,
            credential_material_accessed=response.credential_material_accessed,
        )


def _readiness_reasons(readiness: Optional[LiveExecutionReadinessResult]) -> tuple[str, ...]:
    if readiness is None:
        return ("execution_readiness_required",)
    reasons = []
    if readiness.decision != "ready_for_external_operator":
        reasons.append("execution_readiness_not_ready")
    if readiness.surface_kind != "provider":
        reasons.append("readiness_surface_not_provider")
    if readiness.execution_allowed or readiness.authority_granted or readiness.live_transport_enabled:
        reasons.append("readiness_authority_forbidden")
    if readiness.network_opened or readiness.handler_executed or readiness.external_delivery_opened:
        reasons.append("readiness_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _lease(provider_kind: str) -> RuntimeLease:
    capability_id = _LOCAL_PROVIDER_CAPABILITIES[provider_kind]
    return RuntimeLease(
        lease_id="wave86.lease.provider.{0}".format(provider_kind),
        objective_id="wave86.objective.provider",
        principal_id="wave86.operator",
        run_id="wave86.run.provider.{0}".format(provider_kind),
        allowed_capabilities=(capability_id,),
        credential_scopes=(),
        network_hosts=(),
        budget_limit=100,
        evidence_target="mneme.wave86.live_provider_execution",
        live_transport_allowed=False,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )


def _result(
    *,
    decision: LiveProviderExecutionDecision,
    provider_kind: str,
    provider_decision: Optional[str] = None,
    provider_invoked: bool = False,
    content: Optional[str] = None,
    response_id: Optional[str] = None,
    provider_response: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
    network_opened: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
) -> LiveProviderExecutionResult:
    result = LiveProviderExecutionResult(
        decision=decision,
        provider_kind=provider_kind if provider_kind in _SECRET_SAFE_PROVIDER_KINDS else None,
        provider_decision=provider_decision,
        provider_invoked=provider_invoked,
        content=content,
        response_id=response_id,
        provider_response=provider_response,
        blocked_reasons=blocked_reasons,
        local_only=True,
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=network_opened,
        handler_executed=handler_executed,
        external_delivery_opened=False,
        credential_material_accessed=credential_material_accessed,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


_SECRET_SAFE_PROVIDER_KINDS: Final = {
    "fake",
    "local_llm",
    "openai_compatible",
    "anthropic_metadata",
}


def _no_secret_echo(result: LiveProviderExecutionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
