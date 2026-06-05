from __future__ import annotations

import hashlib
import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import redact_secret_spans

LiveOperatorProofDecision = Literal["recorded", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_SAFE_RISK_LABEL_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,96}$")
_SECRET_PREFIXES: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
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
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveOperatorProofResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveOperatorProofDecision
    proof_id: str
    operator_id: str
    handoff_manifest_id: Optional[str] = None
    execution_plan_id: Optional[str] = None
    proof_ref: Optional[str] = None
    proof_hash: Optional[str] = None
    reviewed_risks: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    operator_reviewed: bool = False
    execution_authorized: bool = False
    material_access_authorized: bool = False
    network_authorized: bool = False
    external_delivery_authorized: bool = False
    proof_material_accessed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveOperatorProofRuntime:
    def record(
        self,
        *,
        proof_id: str,
        operator_id: str,
        handoff_manifest_id: Optional[str] = None,
        execution_plan_id: Optional[str] = None,
        proof_ref: Optional[str] = None,
        reviewed_risks: tuple[str, ...] = (),
    ) -> LiveOperatorProofResult:
        safe_proof_id, proof_secret = _safe_required(proof_id)
        safe_operator_id, operator_secret = _safe_required(operator_id)
        safe_handoff_manifest_id, handoff_secret = _safe_optional(handoff_manifest_id)
        safe_execution_plan_id, execution_secret = _safe_optional(execution_plan_id)
        safe_proof_ref, proof_ref_secret = _safe_optional(proof_ref)
        safe_risks, risks_secret = _safe_risks(reviewed_risks)
        reasons = []
        if safe_proof_id == "":
            reasons.append("proof_id_required")
        if safe_operator_id == "":
            reasons.append("operator_id_required")
        if safe_proof_ref is None:
            reasons.append("proof_ref_required")
        if safe_handoff_manifest_id is None and safe_execution_plan_id is None:
            reasons.append("review_target_required")
        if proof_secret or operator_secret or handoff_secret or execution_secret or proof_ref_secret or risks_secret:
            reasons.append("secret_like_operator_proof_field")

        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: LiveOperatorProofDecision = "blocked" if blocked_reasons else "recorded"
        result = LiveOperatorProofResult(
            decision=decision,
            proof_id=safe_proof_id,
            operator_id=safe_operator_id,
            handoff_manifest_id=safe_handoff_manifest_id,
            execution_plan_id=safe_execution_plan_id,
            proof_ref=safe_proof_ref,
            proof_hash=_proof_hash(
                proof_id=safe_proof_id,
                operator_id=safe_operator_id,
                handoff_manifest_id=safe_handoff_manifest_id,
                execution_plan_id=safe_execution_plan_id,
                proof_ref=safe_proof_ref,
                reviewed_risks=safe_risks,
            )
            if decision == "recorded"
            else None,
            reviewed_risks=safe_risks,
            blocked_reasons=blocked_reasons,
            operator_reviewed=decision == "recorded",
            execution_authorized=False,
            material_access_authorized=False,
            network_authorized=False,
            external_delivery_authorized=False,
            proof_material_accessed=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _safe_required(value: str) -> tuple[str, bool]:
    redacted = redact_secret_spans(value.strip())
    return redacted, redacted != value.strip()


def _safe_optional(value: Optional[str]) -> tuple[Optional[str], bool]:
    if value is None:
        return None, False
    stripped = value.strip()
    if stripped == "":
        return None, False
    redacted = redact_secret_spans(stripped)
    return redacted, redacted != stripped


def _safe_risks(values: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    safe_values = []
    unsafe_seen = False
    for value in values:
        normalized = value.strip()
        if normalized == "":
            continue
        if _unsafe_risk_label(normalized):
            unsafe_seen = True
            safe_values.append(redact_secret_spans(normalized))
            continue
        safe_values.append(normalized)
    return tuple(dict.fromkeys(safe_values)), unsafe_seen


def _unsafe_risk_label(value: str) -> bool:
    lowered = value.lower()
    if any(lowered.startswith(prefix) for prefix in _SECRET_PREFIXES):
        return True
    if "bearer " in lowered or "-----begin" in lowered or "=" in lowered:
        return True
    return _SAFE_RISK_LABEL_PATTERN.fullmatch(value) is None


def _proof_hash(
    *,
    proof_id: str,
    operator_id: str,
    handoff_manifest_id: Optional[str],
    execution_plan_id: Optional[str],
    proof_ref: Optional[str],
    reviewed_risks: tuple[str, ...],
) -> str:
    payload = {
        "proof_id": proof_id,
        "operator_id": operator_id,
        "handoff_manifest_id": handoff_manifest_id,
        "execution_plan_id": execution_plan_id,
        "proof_ref": proof_ref,
        "reviewed_risks": reviewed_risks,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _no_secret_echo(result: LiveOperatorProofResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
