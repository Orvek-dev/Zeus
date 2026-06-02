from __future__ import annotations

from datetime import datetime, timezone
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError

from .models import RuntimeLease, _validate_host, _validate_scoped_id

RuntimeKind = Literal["provider", "mcp", "gateway", "cron", "api_tool", "plugin"]
RuntimeLeaseDecision = Literal["allowed", "blocked"]
_RUNTIME_CAPABILITY_PREFIX: Final[dict[RuntimeKind, str]] = {
    "provider": "provider.",
    "mcp": "mcp.",
    "gateway": "gateway.",
    "cron": "cron.",
    "api_tool": "api.tool.",
    "plugin": "plugin.",
}


class RuntimeIntakeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    runtime_kind: RuntimeKind
    capability_id: str
    requested_capabilities: tuple[str, ...] = ()
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    live_network: bool = False
    budget_required: int = Field(ge=0)
    evidence_target: str

    @field_validator("capability_id", "evidence_target")
    @classmethod
    def _validate_required_scope(cls, value: str, info: ValidationInfo) -> str:
        return _validate_scoped_id(value, info.field_name)

    @field_validator("requested_capabilities")
    @classmethod
    def _validate_requested_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_scoped_id(value, "capability_id") for value in values)

    @field_validator("credential_scope")
    @classmethod
    def _validate_credential_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if normalized == "":
            raise ValueError("credential_scope_empty")
        return normalized

    @field_validator("network_host")
    @classmethod
    def _validate_network_host(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_host(value)


class RuntimeLeaseIntakeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RuntimeLeaseDecision
    reason: str
    runtime_kind: RuntimeKind
    capability_id: str
    authority: Optional[AuthorityContext] = None
    credential_scope_label: Optional[str] = None
    budget_limit: Optional[int] = None
    evidence_target: Optional[str] = None
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True
    redacted_input: Optional[str] = None


class RuntimeLeaseBuilder:
    def authorize(
        self,
        lease: object,
        request: RuntimeIntakeRequest,
        *,
        now: Optional[datetime] = None,
    ) -> RuntimeLeaseIntakeResult:
        if lease is None:
            return _blocked("missing_runtime_lease", request)
        if not isinstance(lease, RuntimeLease):
            return _blocked("malformed_runtime_lease", request)

        timestamp = _to_utc(now) if now is not None else datetime.now(timezone.utc)
        if _to_utc(lease.expires_at) <= timestamp:
            return _blocked("runtime_lease_expired", request, lease=lease)

        requested = _requested_capabilities(request)
        allowed_capabilities = set(lease.allowed_capabilities)
        if not _capabilities_match_runtime_kind(request):
            return _blocked("runtime_kind_capability_mismatch", request, lease=lease)
        if request.capability_id not in allowed_capabilities:
            return _blocked("authority_widening", request, lease=lease)
        if not requested.issubset(allowed_capabilities):
            return _blocked("scope_escalation", request, lease=lease)

        credential = _credential_scope_label(request.credential_scope)
        if credential.decision == "blocked":
            return _blocked(
                "unsafe_credential",
                request,
                lease=lease,
                redacted_input=credential.redacted_input,
            )
        if credential.label is not None and credential.label not in set(lease.credential_scopes):
            return _blocked("authority_widening", request, lease=lease)

        if request.live_network and not lease.live_transport_allowed:
            return _blocked("live_network_without_scope", request, lease=lease)
        if request.live_network and (
            request.network_host is None or request.network_host not in set(lease.network_hosts)
        ):
            return _blocked("live_network_without_scope", request, lease=lease)
        if request.network_host is not None and request.network_host not in set(lease.network_hosts):
            return _blocked("authority_widening", request, lease=lease)

        if request.budget_required > lease.budget_limit:
            return _blocked("over_budget", request, lease=lease)
        if request.evidence_target != lease.evidence_target:
            return _blocked("evidence_scope_bypass", request, lease=lease)

        return RuntimeLeaseIntakeResult(
            decision="allowed",
            reason="runtime_lease_allowed",
            runtime_kind=request.runtime_kind,
            capability_id=request.capability_id,
            authority=self.authority_context(
                lease,
                request,
                credential_scope_label=credential.label,
            ),
            credential_scope_label=credential.label,
            budget_limit=lease.budget_limit,
            evidence_target=lease.evidence_target,
            no_secret_echo=lease.no_secret_echo(),
        )

    def authority_context(
        self,
        lease: RuntimeLease,
        request: RuntimeIntakeRequest,
        *,
        credential_scope_label: Optional[str] = None,
    ) -> AuthorityContext:
        allowed_capabilities = set(lease.allowed_capabilities)
        expected_prefix = _RUNTIME_CAPABILITY_PREFIX[request.runtime_kind]
        requested_capability_ids = tuple(
            capability_id
            for capability_id in _requested_capability_ids(request)
            if capability_id in allowed_capabilities and capability_id.startswith(expected_prefix)
        )
        return AuthorityContext(
            principal_id=lease.principal_id,
            run_id=lease.run_id,
            goal_contract_id=lease.objective_id,
            capability_grants=[
                CapabilityGrant(capability_id=capability_id)
                for capability_id in requested_capability_ids
            ],
            network_grants=[
                NetworkGrant(capability_id=capability_id, network_host=network_host)
                for capability_id in requested_capability_ids
                for network_host in (request.network_host,)
                if request.live_network and lease.live_transport_allowed and network_host is not None
            ],
            credential_grants=[
                CredentialGrant(
                    capability_id=capability_id,
                    credential_scope=credential_scope_label,
                )
                for capability_id in requested_capability_ids
                if credential_scope_label is not None
            ],
        )


class _CredentialDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RuntimeLeaseDecision
    label: Optional[str] = None
    redacted_input: Optional[str] = None


def _requested_capabilities(request: RuntimeIntakeRequest) -> set[str]:
    return set(_requested_capability_ids(request))


def _requested_capability_ids(request: RuntimeIntakeRequest) -> tuple[str, ...]:
    requested = [request.capability_id]
    seen = {request.capability_id}
    for capability_id in request.requested_capabilities:
        if capability_id not in seen:
            requested.append(capability_id)
            seen.add(capability_id)
    return tuple(requested)


def _capabilities_match_runtime_kind(request: RuntimeIntakeRequest) -> bool:
    expected_prefix = _RUNTIME_CAPABILITY_PREFIX[request.runtime_kind]
    return all(
        capability_id.startswith(expected_prefix)
        for capability_id in _requested_capability_ids(request)
    )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _credential_scope_label(raw_value: Optional[str]) -> _CredentialDecision:
    if raw_value is None:
        return _CredentialDecision(decision="allowed")
    try:
        scope = CredentialScope.parse(raw_value)
    except CredentialScopeUnsafeError as exc:
        return _CredentialDecision(
            decision="blocked",
            redacted_input=exc.payload["redacted"],
        )
    except ValueError:
        return _CredentialDecision(decision="blocked")
    return _CredentialDecision(decision="allowed", label=scope.label)


def _blocked(
    reason: str,
    request: RuntimeIntakeRequest,
    *,
    lease: Optional[RuntimeLease] = None,
    redacted_input: Optional[str] = None,
) -> RuntimeLeaseIntakeResult:
    return RuntimeLeaseIntakeResult(
        decision="blocked",
        reason=reason,
        runtime_kind=request.runtime_kind,
        capability_id=request.capability_id,
        budget_limit=None if lease is None else lease.budget_limit,
        evidence_target=None if lease is None else lease.evidence_target,
        redacted_input=redacted_input,
    )
