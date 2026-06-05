from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayExternalDecision = Literal["executed", "blocked"]
GatewayExternalTransportKind = Literal["external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_CLEANUP_RECEIPT: Final = "gateway-external-http-client-closed"


class LiveGatewayExternalClientResult(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    external_delivery_opened: bool = True
    cleanup_receipt: str = _CLEANUP_RECEIPT


class LiveGatewayExternalTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayExternalDecision
    execution_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    delivery_envelope_id: Optional[str]
    transport_kind: Optional[GatewayExternalTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    preflight_bound: bool = False
    gateway_envelope_bound: bool = False
    credential_handoff_bound: bool = False
    remote_executor_preflight_bound: bool = False
    remote_target_bound: bool = False
    delivery_attempted: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    external_delivery_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveGatewayExternalTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        gateway_envelope: LiveGatewayDeliveryResult,
        client_result: Optional[LiveGatewayExternalClientResult],
        execution_ref: str,
    ) -> LiveGatewayExternalTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_policy_reasons(policy, gateway_envelope))
        reasons.extend(_preflight_reasons(preflight, policy, gateway_envelope))
        reasons.extend(_gateway_envelope_reasons(gateway_envelope))
        reasons.extend(_client_reasons(client_result))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                preflight=preflight,
                gateway_envelope=gateway_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                client_result=client_result,
            )
        return _result(
            decision="executed",
            policy=policy,
            preflight=preflight,
            gateway_envelope=gateway_envelope,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, preflight, gateway_envelope, safe_ref),
            client_result=client_result,
            policy_bound=True,
            preflight_bound=True,
            gateway_envelope_bound=True,
            credential_handoff_bound=True,
            remote_executor_preflight_bound=True,
            remote_target_bound=True,
            delivery_attempted=True,
            live_transport_enabled=True,
            execution_allowed=True,
            network_opened=True,
            non_loopback_network_opened=True,
            external_delivery_opened=True,
            controlled_external_side_effects=True,
            handler_executed=True,
        )


def _policy_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or policy.adapter_kind != "gateway":
        reasons.append("gateway_remote_policy_not_ready")
    if policy.remote_target != gateway_envelope.target:
        reasons.append("gateway_remote_target_mismatch")
    if policy.live_transport_enabled or policy.network_opened or policy.handler_executed:
        reasons.append("remote_policy_side_effect_detected")
    if policy.external_delivery_opened or policy.credential_material_accessed:
        reasons.append("remote_policy_side_effect_detected")
    if policy.raw_secret_returned or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _preflight_reasons(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> tuple[str, ...]:
    if preflight is None:
        return ("remote_executor_preflight_required",)
    reasons = []
    if preflight.decision != "preflight_ready" or preflight.adapter_kind != "gateway":
        reasons.append("gateway_preflight_not_ready")
    if policy is not None and preflight.policy_id != policy.policy_id:
        reasons.append("gateway_preflight_policy_mismatch")
    if preflight.remote_target_identity != gateway_envelope.target:
        reasons.append("gateway_preflight_target_mismatch")
    if preflight.network_opened or preflight.live_transport_enabled or preflight.handler_executed:
        reasons.append("gateway_preflight_side_effect_detected")
    if preflight.external_delivery_opened or preflight.raw_secret_returned or not preflight.no_secret_echo:
        reasons.append("gateway_preflight_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _gateway_envelope_reasons(gateway_envelope: LiveGatewayDeliveryResult) -> tuple[str, ...]:
    reasons = []
    if gateway_envelope.decision != "prepared" or not gateway_envelope.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if gateway_envelope.delivery_attempted or gateway_envelope.external_delivery_opened:
        reasons.append("gateway_envelope_side_effect_detected")
    if gateway_envelope.credential_material_accessed or gateway_envelope.raw_secret_returned:
        reasons.append("gateway_envelope_secret_leak_detected")
    if gateway_envelope.live_production_claimed or not gateway_envelope.no_secret_echo:
        reasons.append("gateway_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _client_reasons(client_result: Optional[LiveGatewayExternalClientResult]) -> tuple[str, ...]:
    if client_result is None:
        return ("gateway_external_client_result_required",)
    reasons = []
    if client_result.status_code < 200 or client_result.status_code >= 300:
        reasons.append("gateway_external_http_status_not_success")
    if client_result.latency_ms < 0:
        reasons.append("gateway_external_latency_invalid")
    if not client_result.network_opened or not client_result.non_loopback_network_opened:
        reasons.append("gateway_external_network_not_confirmed")
    if not client_result.external_delivery_opened:
        reasons.append("gateway_external_delivery_not_confirmed")
    if client_result.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("gateway_external_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    gateway_envelope: LiveGatewayDeliveryResult,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "delivery_envelope_id": gateway_envelope.delivery_envelope_id,
        "execution_ref": execution_ref,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-external-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveGatewayExternalDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    gateway_envelope: LiveGatewayDeliveryResult,
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    client_result: Optional[LiveGatewayExternalClientResult] = None,
    **flags: bool,
) -> LiveGatewayExternalTransportResult:
    redacted = None if client_result is None else redact_response(client_result.response_payload)
    result = LiveGatewayExternalTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        delivery_envelope_id=gateway_envelope.delivery_envelope_id,
        transport_kind="external_http",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if client_result is None else client_result.status_code,
        latency_ms=None if client_result is None else client_result.latency_ms,
        redacted_response=redacted,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
