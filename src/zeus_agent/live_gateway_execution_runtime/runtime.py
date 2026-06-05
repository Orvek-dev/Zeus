from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_runtime import default_gateway_adapter_specs
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayExecutionDecision = Literal["planned", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_DRY_RUN_ADAPTERS: Final = frozenset(
    adapter.adapter_id for adapter in default_gateway_adapter_specs() if adapter.fake_smoke_enabled
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


class LiveGatewayExecutionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayExecutionDecision
    adapter_id: str
    target: str
    dispatch_id: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    delivery_planned: bool = False
    target_allowlisted: bool = False
    local_dry_run: bool = True
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


class LiveGatewayExecutionRuntime:
    def dispatch(
        self,
        *,
        readiness: Optional[LiveExecutionReadinessResult],
        adapter_id: str,
        target: str,
        message: str,
    ) -> LiveGatewayExecutionResult:
        safe_adapter_id = redact_secret_spans(adapter_id.strip())
        safe_target = redact_secret_spans(target.strip())
        safe_message = redact_secret_spans(message.strip())
        reasons = list(_readiness_reasons(readiness))
        target_allowlisted = _target_allowlisted(adapter_id=safe_adapter_id, target=safe_target)
        if safe_adapter_id not in _DRY_RUN_ADAPTERS:
            reasons.append("unsupported_gateway_adapter")
        if not target_allowlisted:
            reasons.append("delivery_target_not_allowlisted")
        if safe_message == "":
            reasons.append("message_required")
        if reasons:
            return _result(
                decision="blocked",
                adapter_id=safe_adapter_id,
                target=safe_target,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                target_allowlisted=target_allowlisted,
            )
        return _result(
            decision="planned",
            adapter_id=safe_adapter_id,
            target=safe_target,
            dispatch_id=_dispatch_id(
                readiness=readiness,
                adapter_id=safe_adapter_id,
                target=safe_target,
                message=safe_message,
            ),
            delivery_planned=True,
            target_allowlisted=True,
        )


def _readiness_reasons(readiness: Optional[LiveExecutionReadinessResult]) -> tuple[str, ...]:
    if readiness is None:
        return ("execution_readiness_required",)
    reasons = []
    if readiness.decision != "ready_for_external_operator":
        reasons.append("execution_readiness_not_ready")
    if readiness.surface_kind != "gateway":
        reasons.append("readiness_surface_not_gateway")
    if readiness.execution_allowed or readiness.authority_granted or readiness.live_transport_enabled:
        reasons.append("readiness_authority_forbidden")
    if readiness.network_opened or readiness.handler_executed or readiness.external_delivery_opened:
        reasons.append("readiness_side_effect_detected")
    if readiness.credential_material_accessed or readiness.live_production_claimed:
        reasons.append("readiness_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _target_allowlisted(*, adapter_id: str, target: str) -> bool:
    return target.startswith("{0}://".format(adapter_id))


def _dispatch_id(
    *,
    readiness: Optional[LiveExecutionReadinessResult],
    adapter_id: str,
    target: str,
    message: str,
) -> str:
    payload = {
        "adapter_id": adapter_id,
        "message": message,
        "readiness_id": readiness.readiness_id if readiness is not None else None,
        "target": target,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-dispatch-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveGatewayExecutionDecision,
    adapter_id: str,
    target: str,
    dispatch_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    delivery_planned: bool = False,
    target_allowlisted: bool = False,
) -> LiveGatewayExecutionResult:
    result = LiveGatewayExecutionResult(
        decision=decision,
        adapter_id=adapter_id,
        target=target,
        dispatch_id=dispatch_id,
        blocked_reasons=blocked_reasons,
        delivery_planned=delivery_planned,
        target_allowlisted=target_allowlisted,
        local_dry_run=True,
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


def _no_secret_echo(result: LiveGatewayExecutionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
