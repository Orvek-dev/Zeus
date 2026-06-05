from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_transport_audit_runtime.execution_rules import (
    LiveTransportAdapterKind,
    LiveTransportExecutionResult,
    cleanup_verified,
    controlled_external_side_effects,
    execution_adapter_kind,
    execution_reasons,
    side_effect_reasons as collect_side_effect_reasons,
)
from zeus_agent.live_transport_audit_runtime.secret_echo import no_secret_echo
from zeus_agent.security.credentials import redact_secret_spans

LiveTransportAuditDecision = Literal["audit_ready", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))


class LiveTransportAuditResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveTransportAuditDecision
    audit_id: Optional[str]
    audit_ref: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    execution_id: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    execution_result_bound: bool = False
    cleanup_receipt_verified: bool = False
    external_side_effects_absent: bool = False
    execution_live_transport_seen: bool = False
    post_execution_audit_ready: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    controlled_external_side_effects: bool = False
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveTransportAuditRuntime:
    def audit(
        self,
        *,
        adapter_kind: str,
        execution: Optional[LiveTransportExecutionResult],
        audit_ref: str,
    ) -> LiveTransportAuditResult:
        safe_adapter_kind = adapter_kind.strip()
        safe_audit_ref = _safe_optional(audit_ref)
        reasons = [] if safe_adapter_kind in _ADAPTER_KINDS else ["unsupported_adapter_kind"]
        if safe_audit_ref is None:
            reasons.append("audit_ref_required")
        if execution is None:
            reasons.append("execution_result_required")
            return _result(
                adapter_kind=safe_adapter_kind,
                audit_ref=safe_audit_ref,
                execution=None,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        actual_adapter_kind = execution_adapter_kind(execution)
        if safe_adapter_kind != actual_adapter_kind:
            reasons.append("adapter_kind_mismatch")
        reasons.extend(execution_reasons(adapter_kind=actual_adapter_kind, execution=execution))
        side_effect_reasons = collect_side_effect_reasons(adapter_kind=actual_adapter_kind, execution=execution)
        reasons.extend(side_effect_reasons)
        cleanup_ready = cleanup_verified(
            adapter_kind=actual_adapter_kind,
            cleanup_receipt=execution.cleanup_receipt,
        )
        if not cleanup_ready:
            reasons.append("cleanup_receipt_invalid")
        if reasons:
            return _result(
                adapter_kind=safe_adapter_kind,
                audit_ref=safe_audit_ref,
                execution=execution,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                cleanup_receipt_verified=cleanup_ready,
                external_side_effects_absent=not side_effect_reasons,
            )
        controlled_external = controlled_external_side_effects(execution)
        return _result(
            adapter_kind=safe_adapter_kind,
            audit_ref=safe_audit_ref,
            execution=execution,
            audit_id=_audit_id(
                adapter_kind=actual_adapter_kind,
                execution_id=execution.execution_id,
                audit_ref=safe_audit_ref,
            ),
            execution_result_bound=True,
            cleanup_receipt_verified=True,
            external_side_effects_absent=not controlled_external,
            controlled_external_side_effects=controlled_external,
            execution_live_transport_seen=True,
            post_execution_audit_ready=True,
        )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _audit_id(*, adapter_kind: str, execution_id: Optional[str], audit_ref: Optional[str]) -> str:
    payload = {
        "adapter_kind": adapter_kind,
        "audit_ref": audit_ref,
        "execution_id": execution_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-transport-audit-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    adapter_kind: str,
    audit_ref: Optional[str],
    execution: Optional[LiveTransportExecutionResult],
    audit_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    execution_result_bound: bool = False,
    cleanup_receipt_verified: bool = False,
    external_side_effects_absent: bool = False,
    execution_live_transport_seen: bool = False,
    post_execution_audit_ready: bool = False,
    controlled_external_side_effects: bool = False,
) -> LiveTransportAuditResult:
    kind: Optional[LiveTransportAdapterKind] = None
    if adapter_kind in _ADAPTER_KINDS:
        kind = adapter_kind
    result = LiveTransportAuditResult(
        decision="audit_ready" if post_execution_audit_ready else "blocked",
        audit_id=audit_id,
        audit_ref=audit_ref,
        adapter_kind=kind,
        execution_id=None if execution is None else execution.execution_id,
        cleanup_receipt=None if execution is None else execution.cleanup_receipt,
        blocked_reasons=blocked_reasons,
        execution_result_bound=execution_result_bound,
        cleanup_receipt_verified=cleanup_receipt_verified,
        external_side_effects_absent=external_side_effects_absent,
        execution_live_transport_seen=execution_live_transport_seen,
        post_execution_audit_ready=post_execution_audit_ready,
        live_transport_enabled=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        controlled_external_side_effects=controlled_external_side_effects,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
