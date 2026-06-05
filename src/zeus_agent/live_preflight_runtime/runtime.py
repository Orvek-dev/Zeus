from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationInfo, field_validator

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.live_beta_runtime import (
    LiveBetaActivationRequest,
    LiveBetaActivationResult,
    LiveBetaActivationRuntime,
)
from zeus_agent.live_preflight_runtime.gates import (
    credential_binding_reasons,
    credential_readiness_payload,
    gateway_pairing_payload,
    gateway_pairing_reasons,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans

LivePreflightDecision = Literal["preflight_ready", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
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


class LivePreflightRequest(BaseModel):
    model_config = _MODEL_CONFIG

    preflight_id: str
    approval_id: str
    principal_id: str
    objective_id: str
    surface_kind: Literal["provider", "mcp", "gateway"]
    surface_id: str
    capability_id: str
    evidence_target: str
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    approval_receipt_id: Optional[str] = None
    approval_proof_hash: Optional[str] = None
    probe_healthy: bool = False
    source_pinned: bool = False
    mcp_description: Optional[str] = None
    delivery_target: Optional[str] = None
    allowlisted_delivery_targets: tuple[str, ...] = ()
    budget_required: int = 1
    cleanup_required: bool = True
    live_production_claim_requested: bool = False

    @field_validator(
        "preflight_id",
        "approval_id",
        "principal_id",
        "objective_id",
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
        "approval_proof_hash",
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
    def _validate_targets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "allowlisted_delivery_targets") for value in values)


class LivePreflightResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LivePreflightDecision
    preflight_id: str
    surface_kind: Literal["provider", "mcp", "gateway"]
    surface_id: str
    capability_id: str
    approval_receipt: ApprovalReceiptResult
    activation: LiveBetaActivationResult
    activation_decision: Literal["live_beta", "blocked"]
    credential_readiness: Optional[dict[str, JsonValue]] = None
    credential_bindings_ready: bool = True
    gateway_pairing: Optional[dict[str, JsonValue]] = None
    gateway_pairing_ready: bool = True
    blocked_reasons: tuple[str, ...]
    approval_receipt_bound: bool
    approval_receipt_recorded: bool
    lease_authorized: bool
    cleanup_required: bool
    live_beta_ready: bool
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LivePreflightRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def evaluate(
        self,
        request: LivePreflightRequest,
        *,
        lease: RuntimeLease,
        now: Optional[datetime] = None,
    ) -> LivePreflightResult:
        receipt = ApprovalReceiptRuntime().record(
            approval_id=request.approval_id,
            principal_id=request.principal_id,
            objective_id=request.objective_id,
            capability_id=request.capability_id,
            now=now,
        )
        receipt_reasons = list(_receipt_reasons(request, receipt))
        direct_reasons = list(receipt_reasons)
        if not request.cleanup_required:
            direct_reasons.append("cleanup_plan_required")
        credential_readiness = credential_readiness_payload(self.home)
        credential_reasons = credential_binding_reasons(request, credential_readiness)
        gateway_pairing = gateway_pairing_payload(self.home)
        pairing_reasons = gateway_pairing_reasons(request, gateway_pairing)
        direct_reasons.extend(credential_reasons)
        direct_reasons.extend(pairing_reasons)

        receipt_bound = not receipt_reasons and receipt.approval_receipt_recorded
        activation = LiveBetaActivationRuntime().activate(
            _activation_request(request, receipt_bound=receipt_bound),
            lease=lease,
            now=now,
        )
        direct_reasons.extend("activation:{0}".format(reason) for reason in activation.reasons)
        blocked_reasons = tuple(dict.fromkeys(direct_reasons))
        ready = not blocked_reasons and activation.decision == "live_beta"
        decision: LivePreflightDecision = "preflight_ready" if ready else "blocked"
        result = LivePreflightResult(
            decision=decision,
            preflight_id=redact_secret_spans(request.preflight_id),
            surface_kind=request.surface_kind,
            surface_id=redact_secret_spans(request.surface_id),
            capability_id=redact_secret_spans(request.capability_id),
            approval_receipt=receipt,
            activation=activation,
            activation_decision=activation.decision,
            credential_readiness=credential_readiness,
            credential_bindings_ready=not credential_reasons,
            gateway_pairing=gateway_pairing,
            gateway_pairing_ready=not pairing_reasons,
            blocked_reasons=blocked_reasons,
            approval_receipt_bound=receipt_bound,
            approval_receipt_recorded=receipt.approval_receipt_recorded,
            lease_authorized=activation.lease_authorized,
            cleanup_required=request.cleanup_required,
            live_beta_ready=ready,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=activation.network_opened,
            handler_executed=activation.handler_executed,
            external_delivery_opened=activation.external_delivery_opened,
            credential_material_accessed=activation.credential_material_accessed,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _receipt_reasons(
    request: LivePreflightRequest,
    receipt: ApprovalReceiptResult,
) -> tuple[str, ...]:
    reasons = []
    if not receipt.approval_receipt_recorded:
        reasons.append("approval_receipt_not_recorded")
    reasons.extend(receipt.blocked_reasons)
    if request.approval_receipt_id is None:
        reasons.append("approval_receipt_id_required")
    elif receipt.receipt_id is not None and request.approval_receipt_id != receipt.receipt_id:
        reasons.append("approval_receipt_id_mismatch")
    if request.approval_proof_hash is None:
        reasons.append("approval_proof_hash_required")
    elif receipt.proof_hash is not None and request.approval_proof_hash != receipt.proof_hash:
        reasons.append("approval_proof_hash_mismatch")
    return tuple(dict.fromkeys(reasons))


def _activation_request(
    request: LivePreflightRequest,
    *,
    receipt_bound: bool,
) -> LiveBetaActivationRequest:
    return LiveBetaActivationRequest(
        activation_id="{0}.activation".format(redact_secret_spans(request.preflight_id)),
        surface_kind=request.surface_kind,
        surface_id=redact_secret_spans(request.surface_id),
        capability_id=request.capability_id,
        credential_scope=request.credential_scope,
        network_host=request.network_host,
        evidence_target=request.evidence_target,
        approval_receipt_id=request.approval_receipt_id if receipt_bound else None,
        probe_healthy=request.probe_healthy,
        source_pinned=request.source_pinned,
        mcp_description=request.mcp_description,
        delivery_target=request.delivery_target,
        allowlisted_delivery_targets=request.allowlisted_delivery_targets,
        budget_required=request.budget_required,
        live_production_claim_requested=request.live_production_claim_requested,
    )


def _recommended_next_commands(decision: LivePreflightDecision) -> tuple[str, ...]:
    if decision == "preflight_ready":
        return (
            "zeus live-optin-smoke --scenario happy --json",
            "zeus live --include-smoke --scenario happy --json",
            "zeus security --json",
        )
    return (
        "zeus credentials --json",
        "zeus approval-receipt --json",
        "zeus live-readiness --json",
        "zeus security --json",
    )


def _no_secret_echo(result: LivePreflightResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
