from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.live_transport_audit_runtime.execution_rules import (
    LiveTransportAdapterKind,
    LiveTransportExecutionResult,
    controlled_external_side_effects,
    execution_adapter_kind,
)
from zeus_agent.security.credentials import redact_secret_spans

LiveTransportTeardownDecision = Literal["teardown_recorded", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
_LEDGER_NAME: Final = "live_transport_teardown.jsonl"
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


class LiveTransportTeardownResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveTransportTeardownDecision
    teardown_id: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    execution_id: Optional[str]
    audit_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    teardown_ref: Optional[str]
    cleanup_receipt: Optional[str]
    ledger_path: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    duplicate: bool = False
    policy_bound: bool = False
    preflight_bound: bool = False
    execution_bound: bool = False
    audit_bound: bool = False
    cleanup_receipt_bound: bool = False
    controlled_external_side_effects: bool = False
    ledger_recorded: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveTransportTeardownRuntime:
    def record(
        self,
        *,
        home: Path,
        adapter_kind: str,
        policy: LiveRemoteTransportPolicyResult,
        preflight: LiveRemoteExecutorPreflightResult,
        execution: LiveTransportExecutionResult,
        audit: LiveTransportAuditResult,
        teardown_ref: str,
    ) -> LiveTransportTeardownResult:
        safe_kind = adapter_kind.strip()
        safe_ref = _safe_optional(teardown_ref)
        reasons = list(_reasons(safe_kind, policy, preflight, execution, audit, safe_ref))
        teardown_id = None if reasons else _teardown_id(safe_kind, execution.execution_id, audit.audit_id, safe_ref)
        ledger_path = home / _LEDGER_NAME
        if reasons:
            return _result(
                decision="blocked",
                adapter_kind=safe_kind,
                policy=policy,
                preflight=preflight,
                execution=execution,
                audit=audit,
                teardown_ref=safe_ref,
                ledger_path=ledger_path,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        duplicate = _ledger_has_id(ledger_path, teardown_id or "")
        if not duplicate:
            _append_ledger(ledger_path, _ledger_record(safe_kind, policy, preflight, execution, audit, safe_ref, teardown_id or ""))
        return _result(
            decision="teardown_recorded",
            adapter_kind=safe_kind,
            policy=policy,
            preflight=preflight,
            execution=execution,
            audit=audit,
            teardown_ref=safe_ref,
            ledger_path=ledger_path,
            teardown_id=teardown_id,
            duplicate=duplicate,
            policy_bound=True,
            preflight_bound=True,
            execution_bound=True,
            audit_bound=True,
            cleanup_receipt_bound=True,
            controlled_external=True,
            ledger_recorded=True,
        )


def _reasons(
    adapter_kind: str,
    policy: LiveRemoteTransportPolicyResult,
    preflight: LiveRemoteExecutorPreflightResult,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown_ref: Optional[str],
) -> tuple[str, ...]:
    reasons = []
    if adapter_kind not in _ADAPTER_KINDS:
        reasons.append("unsupported_adapter_kind")
    if adapter_kind in _ADAPTER_KINDS and execution_adapter_kind(execution) != adapter_kind:
        reasons.append("execution_adapter_kind_mismatch")
    if policy.decision != "policy_ready" or policy.adapter_kind != adapter_kind:
        reasons.append("remote_policy_not_ready")
    if preflight.decision != "preflight_ready" or preflight.adapter_kind != adapter_kind:
        reasons.append("remote_preflight_not_ready")
    if execution.decision != "executed" or not controlled_external_side_effects(execution):
        reasons.append("controlled_external_execution_required")
    if audit.decision != "audit_ready" or not audit.controlled_external_side_effects:
        reasons.append("controlled_external_audit_required")
    if policy.policy_id != execution.policy_id or preflight.preflight_id != execution.preflight_id:
        reasons.append("execution_not_policy_preflight_bound")
    if audit.execution_id != execution.execution_id or audit.cleanup_receipt != execution.cleanup_receipt:
        reasons.append("audit_not_execution_bound")
    if teardown_ref is None or policy.teardown_ref != teardown_ref or preflight.teardown_ref != teardown_ref:
        reasons.append("teardown_ref_policy_mismatch")
    if audit.cleanup_receipt_verified is False or execution.cleanup_receipt is None:
        reasons.append("cleanup_receipt_not_verified")
    if policy.live_production_claimed or preflight.live_production_claimed or execution.live_production_claimed:
        reasons.append("production_claim_detected")
    if audit.live_production_claimed:
        reasons.append("production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _teardown_id(adapter_kind: str, execution_id: Optional[str], audit_id: Optional[str], teardown_ref: Optional[str]) -> str:
    payload = {"adapter_kind": adapter_kind, "audit_id": audit_id, "execution_id": execution_id, "teardown_ref": teardown_ref}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-teardown-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _ledger_record(
    adapter_kind: str,
    policy: LiveRemoteTransportPolicyResult,
    preflight: LiveRemoteExecutorPreflightResult,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown_ref: Optional[str],
    teardown_id: str,
) -> dict[str, JsonValue]:
    return {
        "teardown_id": teardown_id,
        "adapter_kind": adapter_kind,
        "policy_id": policy.policy_id,
        "preflight_id": preflight.preflight_id,
        "execution_id": execution.execution_id,
        "audit_id": audit.audit_id,
        "teardown_ref": teardown_ref,
        "cleanup_receipt": execution.cleanup_receipt,
        "controlled_external_side_effects": True,
        "raw_secret_returned": False,
        "live_production_claimed": False,
    }


def _ledger_has_id(path: Path, teardown_id: str) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip() and json.loads(raw_line).get("teardown_id") == teardown_id:
            return True
    return False


def _append_ledger(path: Path, record: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _result(
    *,
    decision: LiveTransportTeardownDecision,
    adapter_kind: str,
    policy: LiveRemoteTransportPolicyResult,
    preflight: LiveRemoteExecutorPreflightResult,
    execution: LiveTransportExecutionResult,
    audit: LiveTransportAuditResult,
    teardown_ref: Optional[str],
    ledger_path: Path,
    teardown_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    duplicate: bool = False,
    policy_bound: bool = False,
    preflight_bound: bool = False,
    execution_bound: bool = False,
    audit_bound: bool = False,
    cleanup_receipt_bound: bool = False,
    controlled_external: bool = False,
    ledger_recorded: bool = False,
) -> LiveTransportTeardownResult:
    kind: Optional[LiveTransportAdapterKind] = adapter_kind if adapter_kind in _ADAPTER_KINDS else None
    result = LiveTransportTeardownResult(
        decision=decision,
        teardown_id=teardown_id,
        adapter_kind=kind,
        execution_id=execution.execution_id,
        audit_id=audit.audit_id,
        policy_id=policy.policy_id,
        preflight_id=preflight.preflight_id,
        teardown_ref=teardown_ref,
        cleanup_receipt=execution.cleanup_receipt,
        ledger_path=str(ledger_path),
        blocked_reasons=blocked_reasons,
        duplicate=duplicate,
        policy_bound=policy_bound,
        preflight_bound=preflight_bound,
        execution_bound=execution_bound,
        audit_bound=audit_bound,
        cleanup_receipt_bound=cleanup_receipt_bound,
        controlled_external_side_effects=controlled_external,
        ledger_recorded=ledger_recorded,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result.to_payload())})


def _no_secret_echo(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
