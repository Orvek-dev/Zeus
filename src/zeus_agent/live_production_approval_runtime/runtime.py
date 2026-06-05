from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult
from zeus_agent.live_production_approval_runtime.models import (
    LiveProductionApprovalDecision,
    LiveProductionApprovalResult,
)
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.live_transport_audit_runtime.execution_rules import (
    LiveTransportAdapterKind,
    LiveTransportExecutionResult,
    controlled_external_side_effects,
    execution_adapter_kind,
)
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownResult
from zeus_agent.security.credentials import redact_secret_spans

_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
_APPROVAL_SCOPE: Final = {
    "provider": ("provider-live", "provider.external.generate"),
    "gateway": ("external-delivery", "gateway.webhook.dispatch"),
    "mcp": ("mcp-live", "mcp.echo"),
}
_REQUIRED_RISKS: Final = {
    "provider": ("network", "credential_material_access", "external_provider_inference", "live_transport", "production_claim"),
    "gateway": ("network", "credential_material_access", "external_delivery", "live_transport", "production_claim"),
    "mcp": ("network", "credential_material_access", "mcp_remote_tool", "live_transport", "production_claim"),
}
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


class LiveProductionApprovalRuntime:
    def approve(
        self,
        *,
        adapter_kind: str,
        execution: LiveTransportExecutionResult,
        audit: LiveTransportAuditResult,
        teardown: LiveTransportTeardownResult,
        approval_receipt: ApprovalReceiptResult,
        operator_proof: LiveOperatorProofResult,
        production_ref: str,
    ) -> LiveProductionApprovalResult:
        safe_kind = adapter_kind.strip()
        safe_ref = _safe_optional(production_ref)
        reasons = list(_execution_reasons(safe_kind, execution))
        reasons.extend(_audit_reasons(safe_kind, execution, audit))
        reasons.extend(_teardown_reasons(safe_kind, execution, audit, teardown))
        reasons.extend(_approval_reasons(safe_kind, approval_receipt))
        reasons.extend(_operator_reasons(safe_kind, operator_proof))
        if safe_ref is None:
            reasons.append("production_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                adapter_kind=safe_kind,
                execution=execution,
                audit=audit,
                teardown=teardown,
                approval_receipt=approval_receipt,
                operator_proof=operator_proof,
                production_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="production_approval_ready",
            adapter_kind=safe_kind,
            execution=execution,
            audit=audit,
            teardown=teardown,
            approval_receipt=approval_receipt,
            operator_proof=operator_proof,
            production_ref=safe_ref,
            production_approval_id=_approval_id(safe_kind, execution, audit, teardown, approval_receipt, operator_proof, safe_ref),
            execution_bound=True,
            audit_bound=True,
            teardown_bound=True,
            approval_receipt_bound=True,
            operator_proof_bound=True,
            required_risks_acknowledged=True,
            controlled_external_side_effects=True,
            production_claim_authorized=True,
        )


def _execution_reasons(adapter_kind: str, execution: LiveTransportExecutionResult) -> tuple[str, ...]:
    reasons = []
    if adapter_kind not in _ADAPTER_KINDS:
        reasons.append("unsupported_adapter_kind")
    elif execution_adapter_kind(execution) != adapter_kind:
        reasons.append("execution_adapter_kind_mismatch")
    if execution.decision != "executed" or not controlled_external_side_effects(execution):
        reasons.append("controlled_external_execution_required")
    if execution.live_production_claimed:
        reasons.append("execution_self_production_claim_detected")
    if execution.credential_material_accessed or execution.raw_secret_returned or not execution.no_secret_echo:
        reasons.append("execution_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def _audit_reasons(adapter_kind: str, execution: LiveTransportExecutionResult, audit: LiveTransportAuditResult) -> tuple[str, ...]:
    reasons = []
    if audit.decision != "audit_ready" or not audit.controlled_external_side_effects:
        reasons.append("controlled_external_audit_required")
    if audit.adapter_kind != adapter_kind or audit.execution_id != execution.execution_id:
        reasons.append("audit_not_execution_bound")
    if audit.cleanup_receipt != execution.cleanup_receipt or not audit.cleanup_receipt_verified:
        reasons.append("audit_cleanup_not_verified")
    if audit.live_production_claimed:
        reasons.append("audit_self_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _teardown_reasons(
    adapter_kind: str,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown: LiveTransportTeardownResult,
) -> tuple[str, ...]:
    reasons = []
    if teardown.decision != "teardown_recorded" or not teardown.ledger_recorded:
        reasons.append("teardown_not_recorded")
    if teardown.adapter_kind != adapter_kind or teardown.execution_id != execution.execution_id:
        reasons.append("teardown_not_execution_bound")
    if teardown.audit_id != audit.audit_id or teardown.cleanup_receipt != execution.cleanup_receipt:
        reasons.append("teardown_not_audit_bound")
    if teardown.live_production_claimed:
        reasons.append("teardown_self_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _approval_reasons(adapter_kind: str, approval_receipt: ApprovalReceiptResult) -> tuple[str, ...]:
    expected = _APPROVAL_SCOPE.get(adapter_kind)
    reasons = []
    if approval_receipt.decision != "recorded" or not approval_receipt.approval_receipt_recorded:
        reasons.append("approval_receipt_not_recorded")
    if expected is not None and (approval_receipt.approval_id, approval_receipt.capability_id) != expected:
        reasons.append("approval_receipt_scope_mismatch")
    if approval_receipt.authority_granted or approval_receipt.live_transport_enabled:
        reasons.append("approval_receipt_authority_side_effect_detected")
    if approval_receipt.live_production_claimed or not approval_receipt.no_secret_echo:
        reasons.append("approval_receipt_secret_or_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _operator_reasons(adapter_kind: str, operator_proof: LiveOperatorProofResult) -> tuple[str, ...]:
    required = set(_REQUIRED_RISKS.get(adapter_kind, ()))
    reasons = []
    if operator_proof.decision != "recorded" or not operator_proof.operator_reviewed:
        reasons.append("operator_proof_not_recorded")
    if not required.issubset(set(operator_proof.reviewed_risks)):
        reasons.append("required_risk_not_acknowledged")
    if operator_proof.network_opened or operator_proof.external_delivery_opened:
        reasons.append("operator_proof_side_effect_detected")
    if operator_proof.credential_material_accessed or operator_proof.live_production_claimed:
        reasons.append("operator_proof_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _approval_id(
    adapter_kind: str,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown: LiveTransportTeardownResult,
    approval_receipt: ApprovalReceiptResult,
    operator_proof: LiveOperatorProofResult,
    production_ref: Optional[str],
) -> str:
    payload = {
        "adapter_kind": adapter_kind,
        "approval_receipt_id": approval_receipt.receipt_id,
        "audit_id": audit.audit_id,
        "execution_id": execution.execution_id,
        "operator_proof_hash": operator_proof.proof_hash,
        "production_ref": production_ref,
        "teardown_id": teardown.teardown_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-production-approval-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProductionApprovalDecision,
    adapter_kind: str,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown: LiveTransportTeardownResult,
    approval_receipt: ApprovalReceiptResult,
    operator_proof: LiveOperatorProofResult,
    production_ref: Optional[str],
    production_approval_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    **flags: bool,
) -> LiveProductionApprovalResult:
    kind: Optional[LiveTransportAdapterKind] = adapter_kind if adapter_kind in _ADAPTER_KINDS else None
    result = LiveProductionApprovalResult(
        decision=decision,
        production_approval_id=production_approval_id,
        adapter_kind=kind,
        execution_id=execution.execution_id,
        audit_id=audit.audit_id,
        teardown_id=teardown.teardown_id,
        approval_receipt_id=approval_receipt.receipt_id,
        operator_proof_id=operator_proof.proof_id,
        production_ref=production_ref,
        blocked_reasons=blocked_reasons,
        live_transport_enabled=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result.to_payload())})


def _no_secret_echo(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
