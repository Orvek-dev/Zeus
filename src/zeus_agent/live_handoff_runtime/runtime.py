from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator

from zeus_agent.live_preflight_runtime import LivePreflightResult
from zeus_agent.security.credentials import redact_secret_spans

LiveHandoffDecision = Literal["handoff_ready", "blocked"]

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


class LiveHandoffRequest(BaseModel):
    model_config = _MODEL_CONFIG

    handoff_id: str
    lease_id: str
    preflight: LivePreflightResult
    operator_note: Optional[str] = None
    production_release_requested: bool = False

    @field_validator("handoff_id", "lease_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("operator_note")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "operator_note")


class LiveHandoffResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveHandoffDecision
    handoff_id: str
    manifest_id: Optional[str]
    lease_id: str
    preflight_id: str
    surface_kind: Literal["provider", "mcp", "gateway"]
    surface_id: str
    capability_id: str
    approval_receipt_id: Optional[str]
    blocked_reasons: tuple[str, ...]
    operator_note: Optional[str] = None
    operator_review_required: bool = True
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    preflight_gate_summary: dict[str, JsonValue] = Field(default_factory=dict)
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveHandoffRuntime:
    def build(self, request: LiveHandoffRequest) -> LiveHandoffResult:
        safe_note, note_secret = _safe_optional_field(request.operator_note)
        reasons = list(_preflight_reasons(request.preflight))
        if request.production_release_requested:
            reasons.append("production_release_forbidden")
        if note_secret:
            reasons.append("secret_like_handoff_field")
        blocked_reasons = tuple(dict.fromkeys(reasons))
        ready = not blocked_reasons
        decision: LiveHandoffDecision = "handoff_ready" if ready else "blocked"
        result = LiveHandoffResult(
            decision=decision,
            handoff_id=redact_secret_spans(request.handoff_id),
            manifest_id=_manifest_id(request) if ready else None,
            lease_id=redact_secret_spans(request.lease_id),
            preflight_id=request.preflight.preflight_id,
            surface_kind=request.preflight.surface_kind,
            surface_id=request.preflight.surface_id,
            capability_id=request.preflight.capability_id,
            approval_receipt_id=request.preflight.approval_receipt.receipt_id,
            blocked_reasons=blocked_reasons,
            operator_note=safe_note,
            operator_review_required=True,
            execution_allowed=False,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            preflight_gate_summary=_preflight_gate_summary(request.preflight),
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _safe_optional_field(value: Optional[str]) -> tuple[Optional[str], bool]:
    if value is None:
        return None, False
    redacted = redact_secret_spans(value)
    return redacted, redacted != value.strip()


def _preflight_reasons(preflight: LivePreflightResult) -> tuple[str, ...]:
    reasons = []
    if preflight.decision != "preflight_ready":
        reasons.append("preflight_not_ready")
    if not preflight.live_beta_ready:
        reasons.append("live_beta_not_ready")
    if not preflight.approval_receipt_bound:
        reasons.append("approval_receipt_not_bound")
    if preflight.network_opened or preflight.handler_executed or preflight.external_delivery_opened:
        reasons.append("preflight_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _preflight_gate_summary(preflight: LivePreflightResult) -> dict[str, JsonValue]:
    credential_readiness = _mapping(preflight.credential_readiness)
    gateway_pairing = _mapping(preflight.gateway_pairing)
    return {
        "credential_bindings_ready": preflight.credential_bindings_ready,
        "credential_required_binding_count": _int_value(
            credential_readiness,
            "required_binding_count",
        ),
        "credential_ready_binding_count": _int_value(credential_readiness, "ready_binding_count"),
        "gateway_pairing_ready": preflight.gateway_pairing_ready,
        "gateway_paired_target_count": _int_value(gateway_pairing, "paired_target_count"),
        "credential_material_accessed": bool(
            preflight.credential_material_accessed
            or credential_readiness.get("credential_material_accessed", False),
        ),
        "proof_material_accessed": bool(gateway_pairing.get("proof_material_accessed", False)),
        "network_opened": bool(
            preflight.network_opened
            or credential_readiness.get("network_opened", False)
            or gateway_pairing.get("network_opened", False),
        ),
        "handler_executed": bool(
            preflight.handler_executed
            or credential_readiness.get("handler_executed", False)
            or gateway_pairing.get("handler_executed", False),
        ),
        "external_delivery_opened": bool(
            preflight.external_delivery_opened
            or credential_readiness.get("external_delivery_opened", False)
            or gateway_pairing.get("external_delivery_opened", False),
        ),
        "live_production_claimed": False,
    }


def _mapping(value: Optional[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    if value is None:
        return {}
    return value


def _int_value(payload: dict[str, JsonValue], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _manifest_id(request: LiveHandoffRequest) -> str:
    payload = {
        "handoff_id": request.handoff_id,
        "lease_id": request.lease_id,
        "preflight_id": request.preflight.preflight_id,
        "approval_receipt_id": request.preflight.approval_receipt.receipt_id,
        "surface_id": request.preflight.surface_id,
        "capability_id": request.preflight.capability_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-handoff-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveHandoffDecision) -> tuple[str, ...]:
    if decision == "handoff_ready":
        return (
            "review live handoff manifest",
            "zeus live --json",
            "zeus security --json",
        )
    return (
        "zeus live-preflight --json",
        "zeus approval-receipt --json",
        "zeus live-readiness --json",
    )


def _no_secret_echo(result: LiveHandoffResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
