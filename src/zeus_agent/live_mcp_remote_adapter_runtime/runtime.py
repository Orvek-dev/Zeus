from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_credential_injection_runtime.enforcement import credential_injection_reasons
from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_mcp_remote_adapter_runtime.models import (
    LiveMcpRemoteAdapterClient,
    LiveMcpRemoteAdapterReceipt,
    LiveMcpRemoteAdapterResult,
)
from zeus_agent.live_mcp_remote_adapter_runtime.rules import (
    claim_reasons,
    client_request,
    preflight_reasons,
    receipt_reasons,
)
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpRemoteAdapterDecision = Literal["executed", "blocked"]

_CLEANUP_RECEIPT: Final = "mcp-remote-adapter-client-closed"


class LiveMcpRemoteAdapterRuntime:
    def execute(
        self,
        *,
        claim: Optional[LiveProductionClaimResult],
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        handoff: Optional[LiveRemoteCredentialHandoffResult],
        credential_injection: Optional[LiveCredentialInjectionResult],
        mcp_envelope: LiveMcpRequestResult,
        client: LiveMcpRemoteAdapterClient,
        execution_ref: str,
    ) -> LiveMcpRemoteAdapterResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(claim_reasons(claim))
        reasons.extend(preflight_reasons(policy, preflight, handoff, mcp_envelope))
        reasons.extend(credential_injection_reasons(
            adapter_kind="mcp",
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            credential_injection=credential_injection,
        ))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        request = None if reasons else client_request(claim, preflight, credential_injection, mcp_envelope)
        if request is None:
            return _result(
                decision="blocked",
                claim=claim,
                policy=policy,
                preflight=preflight,
                handoff=handoff,
                credential_injection=credential_injection,
                mcp_envelope=mcp_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        receipt = client.invoke(request)
        reasons.extend(receipt_reasons(receipt))
        if reasons:
            return _result(
                decision="blocked",
                claim=claim,
                policy=policy,
                preflight=preflight,
                handoff=handoff,
                credential_injection=credential_injection,
                mcp_envelope=mcp_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                receipt=receipt,
                request_constructed=True,
                header_value_ref_bound=True,
                production_claim_bound=True,
                credential_injection_bound=True,
            )
        return _result(
            decision="executed",
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            credential_injection=credential_injection,
            mcp_envelope=mcp_envelope,
            execution_ref=safe_ref,
            execution_id=_execution_id(claim, policy, preflight, handoff, credential_injection, mcp_envelope, safe_ref),
            receipt=receipt,
            mcp_remote_adapter=True,
            production_claim_bound=True,
            credential_injection_bound=True,
            request_constructed=True,
            header_value_ref_bound=True,
            policy_bound=True,
            preflight_bound=True,
            mcp_envelope_bound=True,
            credential_handoff_bound=True,
            remote_executor_preflight_bound=True,
            remote_target_bound=True,
            tool_invoked=True,
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
    claim: Optional[LiveProductionClaimResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    credential_injection: Optional[LiveCredentialInjectionResult],
    mcp_envelope: LiveMcpRequestResult,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "claim_id": None if claim is None else claim.claim_id,
        "execution_ref": execution_ref,
        "handoff_id": None if handoff is None else handoff.handoff_id,
        "credential_injection_id": None if credential_injection is None else credential_injection.injection_id,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
        "request_envelope_id": mcp_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-remote-adapter-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveMcpRemoteAdapterDecision,
    claim: Optional[LiveProductionClaimResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    credential_injection: Optional[LiveCredentialInjectionResult],
    mcp_envelope: LiveMcpRequestResult,
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    receipt: Optional[LiveMcpRemoteAdapterReceipt] = None,
    **flags: bool,
) -> LiveMcpRemoteAdapterResult:
    result = LiveMcpRemoteAdapterResult(
        decision=decision,
        execution_id=execution_id,
        claim_id=None if claim is None else claim.claim_id,
        production_approval_id=None if claim is None else claim.production_approval_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        handoff_id=None if handoff is None else handoff.handoff_id,
        credential_injection_id=None if credential_injection is None else credential_injection.injection_id,
        request_envelope_id=mcp_envelope.request_envelope_id,
        transport_kind="remote_server",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if receipt is None else receipt.status_code,
        latency_ms=None if receipt is None else receipt.latency_ms,
        redacted_response=None if receipt is None else redact_response(receipt.response_payload),
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
