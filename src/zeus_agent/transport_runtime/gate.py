from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import AuthorityContext
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError
from zeus_agent.transport_runtime.manifest import TransportHealth, TransportKind
from zeus_agent.transport_runtime.registry import TransportRegistry


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class TransportExecutionGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    transport_kind: TransportKind
    live_transport: bool = False
    credential_scope: Optional[str] = None

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: str) -> str:
        return _require_non_empty(value, "capability_id")

    @field_validator("credential_scope")
    @classmethod
    def _validate_credential_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "credential_scope")


class TransportExecutionGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked"]
    reason: str
    transport_id: Optional[str] = None
    handler_executed: bool = False
    network_opened: bool = False
    credential_scope_label: Optional[str] = None
    redacted_input: Optional[str] = None


class TransportExecutionGate:
    def __init__(self, registry: TransportRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        request: TransportExecutionGateRequest,
        authority: AuthorityContext,
    ) -> TransportExecutionGateResult:
        credential = _credential_scope_label(request.credential_scope)
        if credential.decision == "blocked":
            return _blocked(
                reason=credential.reason,
                redacted_input=credential.redacted_input,
            )

        manifest = self._registry.manifest_for_capability(request.capability_id)
        if manifest is None:
            return _blocked(reason="unknown_transport_capability")
        if manifest.kind != request.transport_kind:
            return _blocked(
                reason="transport_kind_mismatch",
                transport_id=manifest.transport_id,
            )
        if self._registry.health_for_transport(manifest.transport_id) != TransportHealth.healthy:
            return _blocked(reason="unhealthy_probe", transport_id=manifest.transport_id)
        if request.live_transport or manifest.policy.live_transport:
            return _blocked(
                reason="live_transport_not_authorized",
                transport_id=manifest.transport_id,
            )

        for requirement in manifest.policy.authority_requirements:
            decision = authority.allows(
                requirement.capability_id,
                network_host=requirement.network_host,
                credential_scope=requirement.credential_scope,
            )
            if decision.decision == "blocked":
                return _blocked(reason=decision.reason, transport_id=manifest.transport_id)
        return TransportExecutionGateResult(
            decision="allowed",
            reason="transport_registry_allowed",
            transport_id=manifest.transport_id,
            credential_scope_label=credential.label,
        )


class _CredentialScopeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked"]
    label: Optional[str] = None
    reason: str = "credential_scope_allowed"
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


def _blocked(
    *,
    reason: str,
    transport_id: Optional[str] = None,
    redacted_input: Optional[str] = None,
) -> TransportExecutionGateResult:
    return TransportExecutionGateResult(
        decision="blocked",
        reason=reason,
        transport_id=transport_id,
        redacted_input=redacted_input,
    )
