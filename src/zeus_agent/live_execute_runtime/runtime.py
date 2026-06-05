from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator

from zeus_agent.live_handoff_runtime import LiveHandoffResult
from zeus_agent.security.credentials import redact_secret_spans

LiveExecuteDecision = Literal["planned", "blocked"]

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


class LiveExecutePlanRequest(BaseModel):
    model_config = _MODEL_CONFIG

    execution_id: str
    handoff: LiveHandoffResult
    secret_resolver_plan: Optional[dict[str, JsonValue]] = None
    operator_proof: Optional[dict[str, JsonValue]] = None
    execute_live: bool = False
    dry_run: bool = True
    operator_confirmation: Optional[str] = None

    @field_validator("execution_id")
    @classmethod
    def _validate_execution_id(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("operator_confirmation")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "operator_confirmation")


class LiveExecutePlanResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecuteDecision
    execution_id: str
    execution_plan_id: Optional[str]
    handoff_manifest_id: Optional[str]
    handoff_id: str
    surface_kind: Literal["provider", "mcp", "gateway"]
    surface_id: str
    capability_id: str
    planned_steps: tuple[str, ...]
    cleanup_obligations: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    operator_confirmation: Optional[str] = None
    dry_run: bool = True
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    handoff_gate_summary: dict[str, JsonValue] = Field(default_factory=dict)
    secret_resolver_plan: Optional[dict[str, JsonValue]] = None
    secret_resolver_ready: bool = True
    operator_proof_bound: bool = False
    operator_proof_summary: Optional[dict[str, JsonValue]] = None
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutePlanRuntime:
    def plan(self, request: LiveExecutePlanRequest) -> LiveExecutePlanResult:
        safe_confirmation, confirmation_secret = _safe_optional_field(request.operator_confirmation)
        reasons = list(_handoff_reasons(request.handoff))
        resolver_reasons = _secret_resolver_reasons(request.secret_resolver_plan)
        proof_reasons = _operator_proof_reasons(request.operator_proof)
        reasons.extend(resolver_reasons)
        reasons.extend(proof_reasons)
        if request.execute_live or not request.dry_run:
            reasons.append("live_execution_requires_external_operator")
        if confirmation_secret:
            reasons.append("secret_like_execution_field")
        blocked_reasons = tuple(dict.fromkeys(reasons))
        planned = not blocked_reasons
        decision: LiveExecuteDecision = "planned" if planned else "blocked"
        result = LiveExecutePlanResult(
            decision=decision,
            execution_id=redact_secret_spans(request.execution_id),
            execution_plan_id=_plan_id(request) if planned else None,
            handoff_manifest_id=request.handoff.manifest_id,
            handoff_id=request.handoff.handoff_id,
            surface_kind=request.handoff.surface_kind,
            surface_id=request.handoff.surface_id,
            capability_id=request.handoff.capability_id,
            planned_steps=_planned_steps() if planned else (),
            cleanup_obligations=_cleanup_obligations() if planned else (),
            blocked_reasons=blocked_reasons,
            operator_confirmation=safe_confirmation,
            dry_run=True,
            execution_allowed=False,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            handoff_gate_summary=request.handoff.preflight_gate_summary,
            secret_resolver_plan=request.secret_resolver_plan,
            secret_resolver_ready=not resolver_reasons,
            operator_proof_bound=request.operator_proof is not None and not proof_reasons,
            operator_proof_summary=_operator_proof_summary(request.operator_proof),
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


def _handoff_reasons(handoff: LiveHandoffResult) -> tuple[str, ...]:
    reasons = []
    if handoff.decision != "handoff_ready":
        reasons.append("handoff_not_ready")
    if handoff.manifest_id is None:
        reasons.append("handoff_manifest_missing")
    if handoff.execution_allowed:
        reasons.append("handoff_execution_permission_forbidden")
    if handoff.network_opened or handoff.handler_executed or handoff.external_delivery_opened:
        reasons.append("handoff_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _secret_resolver_reasons(plan: Optional[dict[str, JsonValue]]) -> tuple[str, ...]:
    if plan is None:
        return ()
    reasons = []
    if plan.get("decision") != "planned":
        reasons.append("secret_resolver_not_ready")
    if bool(plan.get("material_access_allowed", False)):
        reasons.append("secret_resolver_material_access_forbidden")
    if (
        bool(plan.get("network_opened", False))
        or bool(plan.get("handler_executed", False))
        or bool(plan.get("external_delivery_opened", False))
        or bool(plan.get("credential_material_accessed", False))
    ):
        reasons.append("secret_resolver_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _operator_proof_reasons(proof: Optional[dict[str, JsonValue]]) -> tuple[str, ...]:
    if proof is None:
        return ()
    reasons = []
    if proof.get("decision") != "recorded":
        reasons.append("operator_proof_not_ready")
    if not bool(proof.get("operator_reviewed", False)):
        reasons.append("operator_review_missing")
    if (
        bool(proof.get("execution_authorized", False))
        or bool(proof.get("material_access_authorized", False))
        or bool(proof.get("network_authorized", False))
        or bool(proof.get("external_delivery_authorized", False))
    ):
        reasons.append("operator_proof_authority_forbidden")
    if (
        bool(proof.get("proof_material_accessed", False))
        or bool(proof.get("credential_material_accessed", False))
        or bool(proof.get("network_opened", False))
        or bool(proof.get("handler_executed", False))
        or bool(proof.get("external_delivery_opened", False))
    ):
        reasons.append("operator_proof_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _operator_proof_summary(proof: Optional[dict[str, JsonValue]]) -> Optional[dict[str, JsonValue]]:
    if proof is None:
        return None
    return {
        "proof_id": proof.get("proof_id"),
        "operator_id": proof.get("operator_id"),
        "handoff_manifest_id": proof.get("handoff_manifest_id"),
        "execution_plan_id": proof.get("execution_plan_id"),
        "proof_hash": proof.get("proof_hash"),
        "reviewed_risks": proof.get("reviewed_risks", []),
        "operator_reviewed": bool(proof.get("operator_reviewed", False)),
        "execution_authorized": False,
        "material_access_authorized": False,
        "network_authorized": False,
        "external_delivery_authorized": False,
        "proof_material_accessed": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _planned_steps() -> tuple[str, ...]:
    return (
        "bind_approval_receipt",
        "bind_runtime_lease",
        "verify_transport_probe",
        "stage_handler_inputs",
        "write_execution_evidence",
    )


def _cleanup_obligations() -> tuple[str, ...]:
    return (
        "write_execution_evidence",
        "close_transport_session",
        "clear_ephemeral_inputs",
    )


def _plan_id(request: LiveExecutePlanRequest) -> str:
    payload = {
        "execution_id": request.execution_id,
        "handoff_manifest_id": request.handoff.manifest_id,
        "handoff_id": request.handoff.handoff_id,
        "capability_id": request.handoff.capability_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execute-plan-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveExecuteDecision) -> tuple[str, ...]:
    if decision == "planned":
        return (
            "review live execute plan",
            "capture operator approval outside Zeus",
            "zeus live --json",
        )
    return (
        "zeus live-handoff --json",
        "zeus live-preflight --json",
        "zeus security --json",
    )


def _no_secret_echo(result: LiveExecutePlanResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
