from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.security.credentials import redact_secret_spans

LiveResponseRedactionDecision = Literal["redacted", "blocked"]

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


class LiveResponseRedactionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResponseRedactionDecision
    redaction_id: Optional[str]
    audit_id: Optional[str]
    audit_ref: Optional[str]
    response_ref: Optional[str]
    redacted_response: Optional[dict[str, JsonValue]]
    blocked_reasons: tuple[str, ...] = ()
    audit_result_bound: bool = False
    response_bound: bool = False
    redaction_applied: bool = False
    no_secret_echo: bool = True
    live_transport_enabled: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResponseRedactionRuntime:
    def redact(
        self,
        *,
        audit: Optional[LiveTransportAuditResult],
        response_payload: dict[str, JsonValue],
        response_ref: str,
    ) -> LiveResponseRedactionResult:
        safe_response_ref = _safe_optional(response_ref)
        reasons = list(_audit_reasons(audit))
        if safe_response_ref is None:
            reasons.append("response_ref_required")
        if reasons:
            return _result(
                audit=audit,
                response_ref=safe_response_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        redacted_response, redaction_applied = _redact_response(response_payload)
        return _result(
            audit=audit,
            response_ref=safe_response_ref,
            redacted_response=redacted_response,
            redaction_id=_redaction_id(
                audit=audit,
                response_ref=safe_response_ref,
                redacted_response=redacted_response,
            ),
            audit_result_bound=True,
            response_bound=True,
            redaction_applied=redaction_applied,
        )


def _audit_reasons(audit: Optional[LiveTransportAuditResult]) -> tuple[str, ...]:
    if audit is None:
        return ("transport_audit_required",)
    reasons = []
    if audit.decision != "audit_ready" or not audit.post_execution_audit_ready:
        reasons.append("transport_audit_not_ready")
    controlled_external = getattr(audit, "controlled_external_side_effects", False)
    if not audit.cleanup_receipt_verified or not (audit.external_side_effects_absent or controlled_external):
        reasons.append("transport_audit_incomplete")
    if audit.live_transport_enabled or audit.network_opened:
        reasons.append("transport_audit_side_effect_detected")
    if audit.credential_material_accessed or audit.raw_secret_returned:
        reasons.append("transport_audit_secret_leak_detected")
    if not audit.no_secret_echo or audit.live_production_claimed:
        reasons.append("transport_audit_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _redact_response(response_payload: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], bool]:
    redacted = {}
    changed = False
    for key, value in response_payload.items():
        redacted_key = redact_secret_spans(key)
        redacted_value, value_changed = _redact_value(value)
        redacted[redacted_key] = redacted_value
        changed = changed or value_changed or redacted_key != key
    return redacted, changed


def _redact_value(value: JsonValue) -> tuple[JsonValue, bool]:
    if isinstance(value, str):
        redacted = redact_secret_spans(value)
        return redacted, redacted != value
    if isinstance(value, list):
        redacted_items = []
        changed = False
        for item in value:
            redacted_item, item_changed = _redact_value(item)
            redacted_items.append(redacted_item)
            changed = changed or item_changed
        return redacted_items, changed
    if isinstance(value, dict):
        redacted_dict = {}
        changed = False
        for key, item in value.items():
            redacted_key = redact_secret_spans(key)
            redacted_item, item_changed = _redact_value(item)
            redacted_dict[redacted_key] = redacted_item
            changed = changed or item_changed or redacted_key != key
        return redacted_dict, changed
    return value, False


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _redaction_id(
    *,
    audit: Optional[LiveTransportAuditResult],
    response_ref: Optional[str],
    redacted_response: dict[str, JsonValue],
) -> str:
    payload = {
        "audit_id": None if audit is None else audit.audit_id,
        "response_ref": response_ref,
        "response": redacted_response,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-response-redaction-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    audit: Optional[LiveTransportAuditResult],
    response_ref: Optional[str],
    redacted_response: Optional[dict[str, JsonValue]] = None,
    redaction_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    audit_result_bound: bool = False,
    response_bound: bool = False,
    redaction_applied: bool = False,
) -> LiveResponseRedactionResult:
    result = LiveResponseRedactionResult(
        decision="redacted" if response_bound else "blocked",
        redaction_id=redaction_id,
        audit_id=None if audit is None else audit.audit_id,
        audit_ref=None if audit is None else audit.audit_ref,
        response_ref=response_ref,
        redacted_response=redacted_response,
        blocked_reasons=blocked_reasons,
        audit_result_bound=audit_result_bound,
        response_bound=response_bound,
        redaction_applied=redaction_applied,
        live_transport_enabled=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveResponseRedactionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
