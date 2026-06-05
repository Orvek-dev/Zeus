from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportRuntime
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_research_owned_client_transport_runtime.models import (
    LiveResearchOwnedClient,
    LiveResearchOwnedClientReceipt,
    LiveResearchOwnedClientTransportResult,
)
from zeus_agent.live_research_owned_client_transport_runtime.rules import (
    client_request,
    external_client_result,
    policy_reasons,
    receipt_reasons,
)
from zeus_agent.security.credentials import redact_secret_spans

LiveResearchOwnedClientDecision = Literal["executed", "blocked"]

_CLEANUP_RECEIPT: Final = "research-owned-client-closed"


class LiveResearchOwnedClientTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveResearchActivationPolicyResult],
        client: LiveResearchOwnedClient,
        execution_ref: str,
    ) -> LiveResearchOwnedClientTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(policy_reasons(policy))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        request = None if reasons else client_request(policy)
        if request is None:
            return _result(
                decision="blocked",
                policy=policy,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        receipt = client.search(request)
        reasons.extend(receipt_reasons(policy, receipt))
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                receipt=receipt,
                request_constructed=True,
            )
        external_result = LiveResearchExternalTransportRuntime().execute(
            policy=policy,
            client_result=external_client_result(receipt),
            execution_ref=safe_ref,
        )
        if external_result.decision != "executed":
            return _result(
                decision="blocked",
                policy=policy,
                execution_ref=safe_ref,
                blocked_reasons=("research_external_transport_not_executed",),
                receipt=receipt,
                external_result=external_result,
                request_constructed=True,
            )
        return _result(
            decision="executed",
            policy=policy,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, safe_ref),
            receipt=receipt,
            external_result=external_result,
            research_owned_client=True,
            request_constructed=True,
            policy_bound=True,
            source_pin_bound=True,
            research_invoked=True,
            live_search_enabled=True,
            execution_allowed=True,
            network_opened=True,
            non_loopback_network_opened=True,
            controlled_external_side_effects=True,
            handler_executed=True,
            client_constructed=True,
        )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(policy: Optional[LiveResearchActivationPolicyResult], execution_ref: Optional[str]) -> str:
    payload = {
        "execution_ref": execution_ref,
        "policy_id": None if policy is None else policy.policy_id,
        "source_pin_ref": None if policy is None else policy.source_pin_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-owned-client-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveResearchOwnedClientDecision,
    policy: Optional[LiveResearchActivationPolicyResult],
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    receipt: Optional[LiveResearchOwnedClientReceipt] = None,
    external_result: Optional[LiveResearchExternalTransportResult] = None,
    **flags: bool,
) -> LiveResearchOwnedClientTransportResult:
    result = LiveResearchOwnedClientTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        source_id=None if policy is None else policy.source_id,
        source_pin_ref=None if receipt is None else receipt.source_pin_ref,
        transport_kind="owned_external_search",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if receipt is None else receipt.status_code,
        latency_ms=None if receipt is None else receipt.latency_ms,
        result_count=None if receipt is None else receipt.result_count,
        redacted_response=None if receipt is None else redact_response(receipt.response_payload),
        external_transport_result=external_result,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
