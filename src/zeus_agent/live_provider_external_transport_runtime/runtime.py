from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_provider_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderExternalDecision = Literal["executed", "blocked"]
ProviderExternalTransportKind = Literal["external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_CLEANUP_RECEIPT: Final = "provider-external-http-client-closed"


class LiveProviderExternalClientResult(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    cleanup_receipt: str = _CLEANUP_RECEIPT


class LiveProviderExternalTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderExternalDecision
    execution_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    request_envelope_id: Optional[str]
    transport_kind: Optional[ProviderExternalTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    preflight_bound: bool = False
    provider_envelope_bound: bool = False
    credential_handoff_bound: bool = False
    remote_executor_preflight_bound: bool = False
    remote_target_bound: bool = False
    provider_invoked: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderExternalTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        provider_envelope: LiveProviderRequestResult,
        client_result: Optional[LiveProviderExternalClientResult],
        execution_ref: str,
    ) -> LiveProviderExternalTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_policy_reasons(policy, provider_envelope))
        reasons.extend(_preflight_reasons(preflight, policy, provider_envelope))
        reasons.extend(_provider_envelope_reasons(provider_envelope))
        reasons.extend(_client_reasons(client_result))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                preflight=preflight,
                provider_envelope=provider_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                client_result=client_result,
            )
        return _result(
            decision="executed",
            policy=policy,
            preflight=preflight,
            provider_envelope=provider_envelope,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, preflight, provider_envelope, safe_ref),
            client_result=client_result,
            policy_bound=True,
            preflight_bound=True,
            provider_envelope_bound=True,
            credential_handoff_bound=True,
            remote_executor_preflight_bound=True,
            remote_target_bound=True,
            provider_invoked=True,
            live_transport_enabled=True,
            execution_allowed=True,
            network_opened=True,
            non_loopback_network_opened=True,
            controlled_external_side_effects=True,
            handler_executed=True,
        )


def _policy_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    provider_envelope: LiveProviderRequestResult,
) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or policy.adapter_kind != "provider":
        reasons.append("provider_remote_policy_not_ready")
    if policy.remote_target != provider_envelope.endpoint:
        reasons.append("provider_remote_target_mismatch")
    if policy.live_transport_enabled or policy.network_opened or policy.handler_executed:
        reasons.append("remote_policy_side_effect_detected")
    if policy.credential_material_accessed or policy.raw_secret_returned or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _preflight_reasons(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    provider_envelope: LiveProviderRequestResult,
) -> tuple[str, ...]:
    if preflight is None:
        return ("remote_executor_preflight_required",)
    reasons = []
    if preflight.decision != "preflight_ready" or preflight.adapter_kind != "provider":
        reasons.append("provider_preflight_not_ready")
    if policy is not None and preflight.policy_id != policy.policy_id:
        reasons.append("provider_preflight_policy_mismatch")
    if preflight.remote_target_identity != provider_envelope.endpoint_host:
        reasons.append("provider_preflight_endpoint_mismatch")
    if preflight.network_opened or preflight.live_transport_enabled or preflight.handler_executed:
        reasons.append("provider_preflight_side_effect_detected")
    if preflight.raw_secret_returned or not preflight.no_secret_echo:
        reasons.append("provider_preflight_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _provider_envelope_reasons(provider_envelope: LiveProviderRequestResult) -> tuple[str, ...]:
    reasons = []
    if provider_envelope.decision != "prepared" or not provider_envelope.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if provider_envelope.provider_invoked or provider_envelope.network_opened:
        reasons.append("provider_envelope_side_effect_detected")
    if provider_envelope.credential_material_accessed or provider_envelope.raw_secret_returned:
        reasons.append("provider_envelope_secret_leak_detected")
    if provider_envelope.live_production_claimed or not provider_envelope.no_secret_echo:
        reasons.append("provider_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _client_reasons(client_result: Optional[LiveProviderExternalClientResult]) -> tuple[str, ...]:
    if client_result is None:
        return ("provider_external_client_result_required",)
    reasons = []
    if client_result.status_code < 200 or client_result.status_code >= 300:
        reasons.append("provider_external_http_status_not_success")
    if client_result.latency_ms < 0:
        reasons.append("provider_external_latency_invalid")
    if not client_result.network_opened or not client_result.non_loopback_network_opened:
        reasons.append("provider_external_network_not_confirmed")
    if client_result.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("provider_external_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    provider_envelope: LiveProviderRequestResult,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "execution_ref": execution_ref,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
        "request_envelope_id": provider_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-external-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProviderExternalDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    provider_envelope: LiveProviderRequestResult,
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    client_result: Optional[LiveProviderExternalClientResult] = None,
    policy_bound: bool = False,
    preflight_bound: bool = False,
    provider_envelope_bound: bool = False,
    credential_handoff_bound: bool = False,
    remote_executor_preflight_bound: bool = False,
    remote_target_bound: bool = False,
    provider_invoked: bool = False,
    live_transport_enabled: bool = False,
    execution_allowed: bool = False,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    controlled_external_side_effects: bool = False,
    handler_executed: bool = False,
) -> LiveProviderExternalTransportResult:
    redacted = None if client_result is None else redact_response(client_result.response_payload)
    result = LiveProviderExternalTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        request_envelope_id=provider_envelope.request_envelope_id,
        transport_kind="external_http",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if network_opened or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        policy_bound=policy_bound,
        preflight_bound=preflight_bound,
        provider_envelope_bound=provider_envelope_bound,
        credential_handoff_bound=credential_handoff_bound,
        remote_executor_preflight_bound=remote_executor_preflight_bound,
        remote_target_bound=remote_target_bound,
        provider_invoked=provider_invoked,
        live_transport_enabled=live_transport_enabled,
        execution_allowed=execution_allowed,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=controlled_external_side_effects,
        handler_executed=handler_executed,
        status_code=None if client_result is None else client_result.status_code,
        latency_ms=None if client_result is None else client_result.latency_ms,
        redacted_response=redacted,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
