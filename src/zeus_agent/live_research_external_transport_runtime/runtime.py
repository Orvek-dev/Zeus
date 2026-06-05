from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.security.credentials import redact_secret_spans

LiveResearchExternalDecision = Literal["executed", "blocked"]
ResearchExternalTransportKind = Literal["external_search"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_CLEANUP_RECEIPT: Final = "research-external-client-closed"


class LiveResearchExternalClientResult(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    source_pin_ref: str
    result_count: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    cleanup_receipt: str = _CLEANUP_RECEIPT


class LiveResearchExternalTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchExternalDecision
    execution_id: Optional[str]
    policy_id: Optional[str]
    source_id: Optional[str]
    source_pin_ref: Optional[str]
    transport_kind: Optional[ResearchExternalTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    source_pin_bound: bool = False
    research_invoked: bool = False
    live_search_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchExternalTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveResearchActivationPolicyResult],
        client_result: Optional[LiveResearchExternalClientResult],
        execution_ref: str,
    ) -> LiveResearchExternalTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_policy_reasons(policy))
        reasons.extend(_client_reasons(policy, client_result))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                client_result=client_result,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="executed",
            policy=policy,
            client_result=client_result,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, client_result, safe_ref),
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


def _policy_reasons(policy: Optional[LiveResearchActivationPolicyResult]) -> tuple[str, ...]:
    if policy is None:
        return ("live_research_policy_required",)
    reasons = []
    if policy.decision != "activation_planned" or not policy.live_search_allowed:
        reasons.append("live_research_policy_not_activation_planned")
    if not policy.approval_bound or not policy.source_pin_bound:
        reasons.append("live_research_policy_missing_controls")
    if policy.network_opened or policy.handler_executed or policy.client_constructed:
        reasons.append("live_research_policy_side_effect_detected")
    if policy.credential_material_accessed or not policy.no_secret_echo:
        reasons.append("live_research_policy_secret_leak_detected")
    if policy.live_production_claimed:
        reasons.append("live_research_policy_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _client_reasons(
    policy: Optional[LiveResearchActivationPolicyResult],
    client_result: Optional[LiveResearchExternalClientResult],
) -> tuple[str, ...]:
    if client_result is None:
        return ("research_external_client_result_required",)
    reasons = []
    if client_result.status_code < 200 or client_result.status_code >= 300:
        reasons.append("research_external_http_status_not_success")
    if client_result.latency_ms < 0:
        reasons.append("research_external_latency_invalid")
    if client_result.result_count < 0:
        reasons.append("research_external_result_count_invalid")
    if policy is not None and client_result.result_count > policy.max_results:
        reasons.append("research_external_result_count_exceeded")
    if policy is not None and client_result.source_pin_ref != policy.source_pin_ref:
        reasons.append("research_source_pin_mismatch")
    if not client_result.network_opened or not client_result.non_loopback_network_opened:
        reasons.append("research_external_network_not_confirmed")
    if client_result.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("research_external_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    policy: Optional[LiveResearchActivationPolicyResult],
    client_result: Optional[LiveResearchExternalClientResult],
    execution_ref: Optional[str],
) -> str:
    payload = {
        "execution_ref": execution_ref,
        "policy_id": None if policy is None else policy.policy_id,
        "source_pin_ref": None if client_result is None else client_result.source_pin_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-external-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveResearchExternalDecision,
    policy: Optional[LiveResearchActivationPolicyResult],
    client_result: Optional[LiveResearchExternalClientResult],
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    **flags: bool,
) -> LiveResearchExternalTransportResult:
    redacted = None if client_result is None else redact_response(client_result.response_payload)
    result = LiveResearchExternalTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        source_id=None if policy is None else policy.source_id,
        source_pin_ref=None if client_result is None else client_result.source_pin_ref,
        transport_kind="external_search",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if client_result is None else client_result.status_code,
        latency_ms=None if client_result is None else client_result.latency_ms,
        result_count=None if client_result is None else client_result.result_count,
        redacted_response=redacted,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
