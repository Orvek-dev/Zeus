from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_production_approval_runtime import LiveProductionApprovalResult
from zeus_agent.live_transport_audit_runtime.execution_rules import LiveTransportAdapterKind
from zeus_agent.security.credentials import redact_secret_spans

LiveProductionClaimDecision = Literal["production_claim_recorded", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_LEDGER_NAME: Final = "live_production_claims.jsonl"
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


class LiveProductionClaimResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProductionClaimDecision
    claim_id: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    production_approval_id: Optional[str]
    claim_ref: Optional[str]
    ledger_path: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    duplicate: bool = False
    approval_bound: bool = False
    production_claim_authorized: bool = False
    production_claim_recorded: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProductionClaimRuntime:
    def record(
        self,
        *,
        home: Path,
        approval: LiveProductionApprovalResult,
        claim_ref: str,
    ) -> LiveProductionClaimResult:
        safe_ref = _safe_optional(claim_ref)
        reasons = list(_approval_reasons(approval))
        if safe_ref is None:
            reasons.append("claim_ref_required")
        ledger_path = home / _LEDGER_NAME
        claim_id = None if reasons else _claim_id(approval, safe_ref)
        if reasons:
            return _result(
                decision="blocked",
                approval=approval,
                claim_ref=safe_ref,
                ledger_path=ledger_path,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        duplicate = _ledger_has_id(ledger_path, claim_id or "")
        if not duplicate:
            _append_ledger(ledger_path, _ledger_record(approval, safe_ref, claim_id or ""))
        return _result(
            decision="production_claim_recorded",
            approval=approval,
            claim_ref=safe_ref,
            ledger_path=ledger_path,
            claim_id=claim_id,
            duplicate=duplicate,
            approval_bound=True,
            production_claim_authorized=True,
            production_claim_recorded=True,
            live_production_claimed=True,
        )


def _approval_reasons(approval: LiveProductionApprovalResult) -> tuple[str, ...]:
    reasons = []
    if approval.decision != "production_approval_ready" or not approval.production_claim_authorized:
        reasons.append("production_approval_not_ready")
    if approval.production_approval_id is None:
        reasons.append("production_approval_id_missing")
    if approval.network_opened or approval.external_delivery_opened:
        reasons.append("production_approval_side_effect_detected")
    if approval.credential_material_accessed or approval.raw_secret_returned:
        reasons.append("production_approval_secret_boundary_failed")
    if approval.live_production_claimed:
        reasons.append("production_approval_self_claim_detected")
    if not approval.no_secret_echo:
        reasons.append("production_approval_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _claim_id(approval: LiveProductionApprovalResult, claim_ref: Optional[str]) -> str:
    payload = {"claim_ref": claim_ref, "production_approval_id": approval.production_approval_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-production-claim-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _ledger_record(approval: LiveProductionApprovalResult, claim_ref: Optional[str], claim_id: str) -> dict[str, JsonValue]:
    return {
        "claim_id": claim_id,
        "adapter_kind": approval.adapter_kind,
        "production_approval_id": approval.production_approval_id,
        "claim_ref": claim_ref,
        "production_claim_authorized": True,
        "live_production_claimed": True,
        "network_opened": False,
        "credential_material_accessed": False,
    }


def _ledger_has_id(path: Path, claim_id: str) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip() and json.loads(raw_line).get("claim_id") == claim_id:
            return True
    return False


def _append_ledger(path: Path, record: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _result(
    *,
    decision: LiveProductionClaimDecision,
    approval: LiveProductionApprovalResult,
    claim_ref: Optional[str],
    ledger_path: Path,
    claim_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    duplicate: bool = False,
    approval_bound: bool = False,
    production_claim_authorized: bool = False,
    production_claim_recorded: bool = False,
    live_production_claimed: bool = False,
) -> LiveProductionClaimResult:
    result = LiveProductionClaimResult(
        decision=decision,
        claim_id=claim_id,
        adapter_kind=approval.adapter_kind,
        production_approval_id=approval.production_approval_id,
        claim_ref=claim_ref,
        ledger_path=str(ledger_path),
        blocked_reasons=blocked_reasons,
        duplicate=duplicate,
        approval_bound=approval_bound,
        production_claim_authorized=production_claim_authorized,
        production_claim_recorded=production_claim_recorded,
        live_transport_enabled=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=live_production_claimed,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result.to_payload())})


def _no_secret_echo(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
