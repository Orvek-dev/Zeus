from __future__ import annotations

import json
from datetime import datetime
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext
from zeus_agent.runtime_lease import (
    RuntimeIntakeRequest,
    RuntimeKind,
    RuntimeLease,
    RuntimeLeaseBuilder,
)
from zeus_agent.security.credentials import redact_secret_spans

LiveBetaSurfaceKind = Literal["provider", "mcp", "gateway"]
LiveBetaDecision = Literal["live_beta", "blocked"]
LiveBetaPayloadValue = Union[str, bool, tuple[str, ...], None]
LiveBetaPayload = dict[str, LiveBetaPayloadValue]

_SURFACE_RUNTIME_KIND: Final[dict[LiveBetaSurfaceKind, RuntimeKind]] = {
    "provider": "provider",
    "mcp": "mcp",
    "gateway": "gateway",
}
_SOURCE_PIN_REQUIRED: Final[tuple[LiveBetaSurfaceKind, ...]] = ("provider", "mcp")
_PROMPT_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "reveal secrets",
    "system prompt",
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class LiveBetaActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    activation_id: str
    surface_kind: LiveBetaSurfaceKind
    surface_id: str
    capability_id: str
    evidence_target: str
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    approval_receipt_id: Optional[str] = None
    probe_healthy: bool = False
    source_pinned: bool = False
    mcp_description: Optional[str] = None
    delivery_target: Optional[str] = None
    allowlisted_delivery_targets: tuple[str, ...] = ()
    budget_required: int = 1
    live_production_claim_requested: bool = False

    @field_validator(
        "activation_id",
        "surface_id",
        "capability_id",
        "evidence_target",
    )
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator(
        "credential_scope",
        "network_host",
        "approval_receipt_id",
        "mcp_description",
        "delivery_target",
    )
    @classmethod
    def _validate_optional_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    @field_validator("allowlisted_delivery_targets")
    @classmethod
    def _validate_allowlisted_targets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "allowlisted_delivery_targets") for value in values)


class LiveBetaActivationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    activation_id: str
    surface_kind: LiveBetaSurfaceKind
    surface_id: str
    capability_id: str
    decision: LiveBetaDecision
    reasons: tuple[str, ...]
    live_beta_claimed: bool
    live_production_claimed: bool = False
    lease_authorized: bool
    approval_receipt_bound: bool
    evidence_target: Optional[str] = None
    credential_scope_label: Optional[str] = None
    redacted_input: Optional[str] = None
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> LiveBetaPayload:
        return {
            "activation_id": self.activation_id,
            "surface_kind": self.surface_kind,
            "surface_id": self.surface_id,
            "capability_id": self.capability_id,
            "decision": self.decision,
            "reasons": self.reasons,
            "live_beta_claimed": self.live_beta_claimed,
            "live_production_claimed": self.live_production_claimed,
            "lease_authorized": self.lease_authorized,
            "approval_receipt_bound": self.approval_receipt_bound,
            "evidence_target": self.evidence_target,
            "credential_scope_label": self.credential_scope_label,
            "redacted_input": self.redacted_input,
            "network_opened": self.network_opened,
            "handler_executed": self.handler_executed,
            "external_delivery_opened": self.external_delivery_opened,
            "credential_material_accessed": self.credential_material_accessed,
            "no_secret_echo": self.no_secret_echo,
        }


class LiveBetaActivationRuntime:
    def activate(
        self,
        request: LiveBetaActivationRequest,
        *,
        lease: RuntimeLease | None,
        now: Optional[datetime] = None,
    ) -> LiveBetaActivationResult:
        intake = RuntimeIntakeRequest(
            runtime_kind=_SURFACE_RUNTIME_KIND[request.surface_kind],
            capability_id=request.capability_id,
            credential_scope=request.credential_scope,
            network_host=request.network_host,
            live_network=True,
            budget_required=request.budget_required,
            evidence_target=request.evidence_target,
        )
        lease_result = RuntimeLeaseBuilder().authorize(lease, intake, now=now)
        reasons = []
        redacted_inputs = []
        if lease_result.decision == "blocked":
            reasons.append(lease_result.reason)
        if lease_result.redacted_input is not None:
            redacted_inputs.append(lease_result.redacted_input)
        reasons.extend(_request_reasons(request))

        approval_receipt_bound = False
        if lease_result.authority is not None and request.approval_receipt_id is not None:
            approval_receipt_bound = _approval_bound(
                lease_result.authority,
                request.capability_id,
            )
            if not approval_receipt_bound:
                reasons.append("approval_outside_authority")
        redacted_inputs.extend(_redacted_inputs(request))
        deduped_reasons = tuple(dict.fromkeys(reasons))
        decision: LiveBetaDecision = "blocked" if deduped_reasons else "live_beta"
        result = LiveBetaActivationResult(
            activation_id=redact_secret_spans(request.activation_id),
            surface_kind=request.surface_kind,
            surface_id=redact_secret_spans(request.surface_id),
            capability_id=request.capability_id,
            decision=decision,
            reasons=deduped_reasons,
            live_beta_claimed=decision == "live_beta",
            lease_authorized=lease_result.decision == "allowed",
            approval_receipt_bound=approval_receipt_bound,
            evidence_target=lease_result.evidence_target,
            credential_scope_label=lease_result.credential_scope_label,
            redacted_input=_join_redacted_inputs(tuple(redacted_inputs)),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _request_reasons(request: LiveBetaActivationRequest) -> tuple[str, ...]:
    reasons = []
    if request.approval_receipt_id is None:
        reasons.append("missing_approval")
    if not request.probe_healthy:
        reasons.append("unhealthy_probe")
    if request.live_production_claim_requested:
        reasons.append("production_claim_forbidden")
    if request.surface_kind in _SOURCE_PIN_REQUIRED and not request.source_pinned:
        reasons.append("adapter_source_unpinned")
    if request.surface_kind == "mcp" and _mcp_prompt_injection_detected(request):
        reasons.append("mcp_prompt_injection")
    if request.surface_kind == "gateway":
        reasons.extend(_gateway_reasons(request))
    return tuple(reasons)


def _gateway_reasons(request: LiveBetaActivationRequest) -> tuple[str, ...]:
    if request.delivery_target is None:
        return ("delivery_target_missing",)
    if request.delivery_target not in set(request.allowlisted_delivery_targets):
        return ("delivery_target_not_allowlisted",)
    return ()


def _mcp_prompt_injection_detected(request: LiveBetaActivationRequest) -> bool:
    description = (request.mcp_description or "").lower()
    return any(marker in description for marker in _PROMPT_INJECTION_MARKERS)


def _approval_bound(authority: AuthorityContext, capability_id: str) -> bool:
    receipt = ApprovalReceipt(
        principal_id=authority.principal_id,
        run_id=authority.run_id,
        goal_contract_id=authority.goal_contract_id,
        approved_capabilities=[capability_id],
    )
    try:
        receipt.assert_within_authority(authority)
    except ValueError:
        return False
    return True


def _redacted_inputs(request: LiveBetaActivationRequest) -> tuple[str, ...]:
    candidates = (
        request.credential_scope,
        request.approval_receipt_id,
        request.delivery_target,
    )
    redacted = []
    for candidate in candidates:
        if candidate is None:
            continue
        safe_value = redact_secret_spans(candidate)
        if safe_value != candidate:
            redacted.append(safe_value)
    return tuple(redacted)


def _join_redacted_inputs(values: tuple[str, ...]) -> Optional[str]:
    deduped = tuple(dict.fromkeys(values))
    if not deduped:
        return None
    return ";".join(deduped)


def _no_secret_echo(result: LiveBetaActivationResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
