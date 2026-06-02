from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError
from zeus_agent.workflow_runtime.jobs import RetryPolicy


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class RollbackPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str
    target: str
    executed: bool = False

    @field_validator("command", "target")
    @classmethod
    def _validate_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class LiveTransportPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    promotion_id: str
    capability_id: str
    transport_kind: Literal["provider", "mcp", "api", "plugin"]
    idempotency_key: str
    retry_policy: RetryPolicy
    rollback_plan: RollbackPlan
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None

    @field_validator("promotion_id", "capability_id", "idempotency_key")
    @classmethod
    def _validate_ids(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("credential_scope", "network_host")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class LiveTransportPromotionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    promotion_id: str
    capability_id: str
    transport_kind: Literal["provider", "mcp", "api", "plugin"]
    decision: Literal["allowed", "blocked"]
    reason: str
    approval_required: bool
    handler_executed: bool = False
    network_opened: bool = False
    retry_policy: dict[str, int]
    rollback_plan: dict[str, object]
    idempotency_key: str
    credential_scope_label: Optional[str] = None
    redacted_input: Optional[str] = None


class LiveTransportPromotionGuard:
    def __init__(self, *, live_transport_enabled: bool = False) -> None:
        self._live_transport_enabled = live_transport_enabled

    def evaluate(
        self,
        request: LiveTransportPromotionRequest,
        *,
        authority: Optional[AuthorityContext] = None,
        approval_receipt: Optional[ApprovalReceipt] = None,
    ) -> LiveTransportPromotionResult:
        credential = _credential_scope_label(request.credential_scope)
        if credential.decision == "blocked":
            return _result(
                request,
                decision="blocked",
                reason=credential.reason or "credential_scope_invalid",
                approval_required=True,
                credential_scope_label=None,
                redacted_input=credential.redacted_input,
            )
        if not self._live_transport_enabled:
            return _result(
                request,
                decision="blocked",
                reason="live_transport_not_authorized",
                approval_required=True,
                credential_scope_label=credential.label,
            )
        if authority is None or approval_receipt is None:
            return _result(
                request,
                decision="blocked",
                reason="live_transport_not_authorized",
                approval_required=True,
                credential_scope_label=credential.label,
            )
        if request.capability_id not in set(approval_receipt.approved_capabilities):
            return _result(
                request,
                decision="blocked",
                reason="approval_missing_capability",
                approval_required=True,
                credential_scope_label=credential.label,
            )
        try:
            approval_receipt.assert_within_authority(authority)
        except ValueError:
            return _result(
                request,
                decision="blocked",
                reason="approval_outside_authority",
                approval_required=True,
                credential_scope_label=credential.label,
            )
        decision = authority.allows(
            request.capability_id,
            network_host=request.network_host,
            credential_scope=credential.label,
        )
        if decision.decision == "blocked":
            return _result(
                request,
                decision="blocked",
                reason=decision.reason,
                approval_required=True,
                credential_scope_label=credential.label,
            )
        return _result(
            request,
            decision="allowed",
            reason="live_transport_authorized",
            approval_required=False,
            credential_scope_label=credential.label,
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


def _result(
    request: LiveTransportPromotionRequest,
    *,
    decision: Literal["allowed", "blocked"],
    reason: str,
    approval_required: bool,
    credential_scope_label: Optional[str],
    redacted_input: Optional[str] = None,
) -> LiveTransportPromotionResult:
    return LiveTransportPromotionResult(
        promotion_id=request.promotion_id,
        capability_id=request.capability_id,
        transport_kind=request.transport_kind,
        decision=decision,
        reason=reason,
        approval_required=approval_required,
        retry_policy={
            "max_attempts": request.retry_policy.max_attempts,
            "backoff_seconds": request.retry_policy.backoff_seconds,
        },
        rollback_plan=request.rollback_plan.model_dump(mode="json"),
        idempotency_key=request.idempotency_key,
        credential_scope_label=credential_scope_label,
        redacted_input=redacted_input,
    )
