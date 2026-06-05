from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from zeus_agent.live_provider_owned_client_transport_runtime.models import (
    LiveProviderOwnedClient,
    LiveProviderOwnedClientReceipt,
    LiveProviderOwnedClientTransportResult,
)
from zeus_agent.live_provider_owned_client_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_provider_owned_client_transport_runtime.rules import (
    client_request,
    preflight_reasons,
    receipt_reasons,
)
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderOwnedClientDecision = Literal["executed", "blocked"]

_CLEANUP_RECEIPT: Final = "provider-owned-client-closed"


class LiveProviderOwnedClientTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        handoff: Optional[LiveRemoteCredentialHandoffResult],
        provider_envelope: LiveProviderRequestResult,
        client: LiveProviderOwnedClient,
        execution_ref: str,
    ) -> LiveProviderOwnedClientTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(preflight_reasons(policy, preflight, handoff, provider_envelope))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        request = None if reasons else client_request(preflight, handoff, provider_envelope)
        if request is None:
            return _result(
                decision="blocked",
                policy=policy,
                preflight=preflight,
                handoff=handoff,
                provider_envelope=provider_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        receipt = client.send(request)
        reasons.extend(receipt_reasons(receipt))
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                preflight=preflight,
                handoff=handoff,
                provider_envelope=provider_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                receipt=receipt,
                request_constructed=True,
                header_value_ref_bound=True,
            )
        return _result(
            decision="executed",
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            provider_envelope=provider_envelope,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, preflight, handoff, provider_envelope, safe_ref),
            receipt=receipt,
            provider_owned_client=True,
            request_constructed=True,
            header_value_ref_bound=True,
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


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    provider_envelope: LiveProviderRequestResult,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "execution_ref": execution_ref,
        "handoff_id": None if handoff is None else handoff.handoff_id,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
        "request_envelope_id": provider_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-owned-client-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProviderOwnedClientDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    provider_envelope: LiveProviderRequestResult,
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    receipt: Optional[LiveProviderOwnedClientReceipt] = None,
    **flags: bool,
) -> LiveProviderOwnedClientTransportResult:
    result = LiveProviderOwnedClientTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        handoff_id=None if handoff is None else handoff.handoff_id,
        request_envelope_id=provider_envelope.request_envelope_id,
        transport_kind="external_http",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if receipt is None else receipt.status_code,
        latency_ms=None if receipt is None else receipt.latency_ms,
        redacted_response=None if receipt is None else redact_response(receipt.response_payload),
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
