from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeLease, RuntimeLeaseBuilder

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_SUPPORTED_RUNTIME_KINDS: Final = frozenset(("provider", "mcp", "gateway"))
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


class LiveTransportLeaseResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    transport_lease_id: Optional[str]
    lease_id: Optional[str]
    runtime_kind: str
    capability_id: str
    network_host: Optional[str]
    credential_scope_label: Optional[str] = None
    authority_context_summary: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    lease_authorized: bool = False
    transport_lease_bound: bool = False
    live_network_requested: bool = True
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


class LiveTransportLeaseRuntime:
    def bind(
        self,
        *,
        readiness: Optional[LiveExecutionReadinessResult],
        lease: Optional[RuntimeLease],
        runtime_kind: str,
        capability_id: str,
        credential_scope: Optional[str],
        network_host: Optional[str],
        budget_required: int,
        evidence_target: str,
        now: Optional[datetime] = None,
    ) -> LiveTransportLeaseResult:
        safe_runtime_kind = runtime_kind.strip()
        safe_capability_id = capability_id.strip()
        safe_network_host = None if network_host is None else network_host.strip()
        safe_evidence_target = evidence_target.strip()
        reasons = list(
            _readiness_reasons(
                readiness,
                runtime_kind=safe_runtime_kind,
                capability_id=safe_capability_id,
            ),
        )
        if safe_runtime_kind not in _SUPPORTED_RUNTIME_KINDS:
            reasons.append("unsupported_live_runtime_kind")
        if reasons:
            return _result(
                decision="blocked",
                runtime_kind=safe_runtime_kind,
                capability_id=safe_capability_id,
                network_host=safe_network_host,
                lease_id=None if lease is None else lease.lease_id,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )

        try:
            request = RuntimeIntakeRequest(
                runtime_kind=safe_runtime_kind,
                capability_id=safe_capability_id,
                credential_scope=credential_scope,
                network_host=safe_network_host,
                live_network=True,
                budget_required=budget_required,
                evidence_target=safe_evidence_target,
            )
        except ValidationError:
            return _result(
                decision="blocked",
                runtime_kind=safe_runtime_kind,
                capability_id=safe_capability_id,
                network_host=safe_network_host,
                lease_id=None if lease is None else lease.lease_id,
                blocked_reasons=("malformed_transport_lease_request",),
            )

        authorized = RuntimeLeaseBuilder().authorize(lease, request, now=now)
        if authorized.decision == "blocked":
            return _result(
                decision="blocked",
                runtime_kind=safe_runtime_kind,
                capability_id=safe_capability_id,
                network_host=safe_network_host,
                lease_id=None if lease is None else lease.lease_id,
                blocked_reasons=("runtime_lease_{0}".format(authorized.reason),),
            )
        return _result(
            decision="bound",
            runtime_kind=safe_runtime_kind,
            capability_id=safe_capability_id,
            network_host=safe_network_host,
            lease_id=None if lease is None else lease.lease_id,
            transport_lease_id=_transport_lease_id(
                readiness=readiness,
                lease=lease,
                request=request,
            ),
            credential_scope_label=authorized.credential_scope_label,
            authority_context_summary=_authority_summary(authorized.authority),
            lease_authorized=True,
            transport_lease_bound=True,
        )


def _readiness_reasons(
    readiness: Optional[LiveExecutionReadinessResult],
    *,
    runtime_kind: str,
    capability_id: str,
) -> tuple[str, ...]:
    if readiness is None:
        return ("execution_readiness_required",)
    reasons = []
    if readiness.decision != "ready_for_external_operator":
        reasons.append("execution_readiness_not_ready")
    if readiness.surface_kind != runtime_kind:
        reasons.append("readiness_surface_mismatch")
    if readiness.capability_id != capability_id:
        reasons.append("readiness_capability_mismatch")
    if readiness.execution_allowed or readiness.authority_granted or readiness.live_transport_enabled:
        reasons.append("readiness_authority_forbidden")
    if readiness.network_opened or readiness.handler_executed or readiness.external_delivery_opened:
        reasons.append("readiness_side_effect_detected")
    if readiness.credential_material_accessed or readiness.live_production_claimed:
        reasons.append("readiness_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _transport_lease_id(
    *,
    readiness: Optional[LiveExecutionReadinessResult],
    lease: Optional[RuntimeLease],
    request: RuntimeIntakeRequest,
) -> str:
    payload = {
        "capability_id": request.capability_id,
        "credential_scope": request.credential_scope,
        "lease_id": None if lease is None else lease.lease_id,
        "network_host": request.network_host,
        "readiness_id": None if readiness is None else readiness.readiness_id,
        "runtime_kind": request.runtime_kind,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-transport-lease-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _authority_summary(value: object) -> Optional[dict[str, JsonValue]]:
    if value is None:
        return None
    payload = value.model_dump(mode="json")
    return {
        "capability_grants": payload.get("capability_grants", []),
        "credential_grants": payload.get("credential_grants", []),
        "network_grants": payload.get("network_grants", []),
        "principal_id": payload.get("principal_id", ""),
        "run_id": payload.get("run_id", ""),
    }


def _result(
    *,
    decision: str,
    runtime_kind: str,
    capability_id: str,
    network_host: Optional[str],
    lease_id: Optional[str],
    transport_lease_id: Optional[str] = None,
    credential_scope_label: Optional[str] = None,
    authority_context_summary: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
    lease_authorized: bool = False,
    transport_lease_bound: bool = False,
) -> LiveTransportLeaseResult:
    result = LiveTransportLeaseResult(
        decision=decision,
        transport_lease_id=transport_lease_id,
        lease_id=lease_id,
        runtime_kind=runtime_kind,
        capability_id=capability_id,
        network_host=network_host,
        credential_scope_label=credential_scope_label,
        authority_context_summary=authority_context_summary,
        blocked_reasons=blocked_reasons,
        lease_authorized=lease_authorized,
        transport_lease_bound=transport_lease_bound,
        live_network_requested=True,
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


def _no_secret_echo(result: LiveTransportLeaseResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
