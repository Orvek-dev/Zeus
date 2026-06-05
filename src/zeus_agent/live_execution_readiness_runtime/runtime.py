from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execute_runtime import LiveExecutePlanResult

LiveExecutionReadinessDecision = Literal["ready_for_external_operator", "blocked"]

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


class LiveExecutionReadinessResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionReadinessDecision
    readiness_id: Optional[str]
    execution_plan_id: Optional[str]
    handoff_manifest_id: Optional[str]
    surface_kind: Literal["provider", "mcp", "gateway"]
    surface_id: str
    capability_id: str
    credential_bindings_ready: bool
    gateway_pairing_ready: bool
    secret_resolver_ready: bool
    operator_proof_bound: bool
    blocked_reasons: tuple[str, ...]
    gate_summary: dict[str, JsonValue]
    operator_proof_summary: Optional[dict[str, JsonValue]] = None
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutionReadinessRuntime:
    def evaluate(self, execute_plan: LiveExecutePlanResult) -> LiveExecutionReadinessResult:
        gate_summary = dict(execute_plan.handoff_gate_summary)
        credential_ready = bool(gate_summary.get("credential_bindings_ready", True))
        gateway_ready = bool(gate_summary.get("gateway_pairing_ready", True))
        reasons = list(
            _readiness_reasons(
                execute_plan,
                credential_ready=credential_ready,
                gateway_ready=gateway_ready,
            ),
        )
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: LiveExecutionReadinessDecision = (
            "blocked" if blocked_reasons else "ready_for_external_operator"
        )
        result = LiveExecutionReadinessResult(
            decision=decision,
            readiness_id=_readiness_id(execute_plan) if decision == "ready_for_external_operator" else None,
            execution_plan_id=execute_plan.execution_plan_id,
            handoff_manifest_id=execute_plan.handoff_manifest_id,
            surface_kind=execute_plan.surface_kind,
            surface_id=execute_plan.surface_id,
            capability_id=execute_plan.capability_id,
            credential_bindings_ready=credential_ready,
            gateway_pairing_ready=gateway_ready,
            secret_resolver_ready=execute_plan.secret_resolver_ready,
            operator_proof_bound=execute_plan.operator_proof_bound,
            blocked_reasons=blocked_reasons,
            gate_summary=gate_summary,
            operator_proof_summary=execute_plan.operator_proof_summary,
            execution_allowed=False,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _readiness_reasons(
    execute_plan: LiveExecutePlanResult,
    *,
    credential_ready: bool,
    gateway_ready: bool,
) -> tuple[str, ...]:
    reasons = []
    if execute_plan.decision != "planned":
        reasons.append("execute_plan_not_planned")
    if execute_plan.execution_plan_id is None:
        reasons.append("execution_plan_id_missing")
    if not credential_ready:
        reasons.append("credential_bindings_not_ready")
    if not gateway_ready:
        reasons.append("gateway_pairing_not_ready")
    if not execute_plan.secret_resolver_ready:
        reasons.append("secret_resolver_not_ready")
    if not execute_plan.operator_proof_bound:
        reasons.append("operator_proof_required")
    if _forbidden_authority(execute_plan):
        reasons.append("execute_plan_authority_forbidden")
    if _side_effect_seen(execute_plan):
        reasons.append("execute_plan_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _forbidden_authority(execute_plan: LiveExecutePlanResult) -> bool:
    return bool(
        execute_plan.execution_allowed
        or execute_plan.authority_granted
        or execute_plan.live_transport_enabled
        or execute_plan.live_production_claimed
    )


def _side_effect_seen(execute_plan: LiveExecutePlanResult) -> bool:
    return bool(
        execute_plan.network_opened
        or execute_plan.handler_executed
        or execute_plan.external_delivery_opened
        or execute_plan.credential_material_accessed
    )


def _readiness_id(execute_plan: LiveExecutePlanResult) -> str:
    payload = {
        "execution_plan_id": execute_plan.execution_plan_id,
        "handoff_manifest_id": execute_plan.handoff_manifest_id,
        "operator_proof": execute_plan.operator_proof_summary,
        "secret_resolver": execute_plan.secret_resolver_plan,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-readiness-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(result: LiveExecutionReadinessResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
