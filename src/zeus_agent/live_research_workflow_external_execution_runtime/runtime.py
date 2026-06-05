from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_workflow_external_execution_runtime.models import (
    LiveResearchWorkflowExternalExecutionResult,
    ResearchWorkflowExternalExecutionDecision,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightResult,
)
from zeus_agent.security.credentials import redact_secret_spans

_EXTERNAL_CLEANUP_RECEIPT: Final = "research-external-client-closed"
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowExternalExecutionRuntime:
    def record(
        self,
        *,
        preflight: LiveResearchWorkflowExternalPreflightResult,
        external_result: Optional[LiveResearchExternalTransportResult] = None,
        owned_client_result: Optional[LiveResearchOwnedClientTransportResult] = None,
        execution_record_ref: str,
    ) -> LiveResearchWorkflowExternalExecutionResult:
        safe_record_ref, secret_seen = _safe_optional(execution_record_ref)
        resolved_external, owned_reasons = _resolve_external_result(external_result, owned_client_result)
        reasons = list(owned_reasons)
        reasons.extend(_input_reasons(safe_record_ref=safe_record_ref, secret_seen=secret_seen))
        reasons.extend(_preflight_reasons(preflight))
        reasons.extend(_external_reasons(resolved_external))
        reasons.extend(_match_reasons(preflight, resolved_external))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowExternalExecutionDecision = (
            "blocked" if blocked_reasons else "external_execution_recorded"
        )
        ready = decision == "external_execution_recorded"
        result = LiveResearchWorkflowExternalExecutionResult(
            decision=decision,
            execution_id=_execution_id(preflight, resolved_external, safe_record_ref) if ready else None,
            execution_record_ref=safe_record_ref,
            preflight_id=preflight.preflight_id,
            preflight_ref=preflight.preflight_ref,
            external_execution_ref=preflight.external_execution_ref,
            external_transport_execution_id=(
                None if resolved_external is None else resolved_external.execution_id
            ),
            owned_client_execution_id=(
                None if owned_client_result is None else owned_client_result.execution_id
            ),
            handoff_manifest_id=preflight.handoff_manifest_id,
            policy_id=preflight.policy_id,
            source_id=preflight.source_id,
            source_pin_ref=preflight.source_pin_ref,
            cleanup_receipt=(
                None if resolved_external is None else resolved_external.cleanup_receipt
            ),
            blocked_reasons=blocked_reasons,
            workflow_external_preflight_bound=ready,
            external_result_bound=ready and resolved_external is not None,
            owned_client_result_bound=ready and owned_client_result is not None,
            policy_bound=ready,
            source_pin_bound=ready,
            research_invoked=ready,
            live_search_enabled=ready,
            execution_allowed=ready,
            external_transport_executed=ready,
            external_network_seen=False if resolved_external is None else resolved_external.network_opened,
            external_non_loopback_network_seen=(
                False if resolved_external is None else resolved_external.non_loopback_network_opened
            ),
            external_cleanup_receipt_bound=ready,
            controlled_external_side_effects_seen=(
                False
                if resolved_external is None
                else resolved_external.controlled_external_side_effects
            ),
            live_transport_enabled=False,
            network_opened=False,
            non_loopback_network_opened=False,
            handler_executed=False,
            client_constructed=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            status_code=None if resolved_external is None else resolved_external.status_code,
            latency_ms=None if resolved_external is None else resolved_external.latency_ms,
            result_count=None if resolved_external is None else resolved_external.result_count,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _resolve_external_result(
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
) -> tuple[Optional[LiveResearchExternalTransportResult], tuple[str, ...]]:
    if owned_client_result is None:
        return external_result, ()
    reasons: list[str] = []
    if owned_client_result.decision != "executed" or not owned_client_result.research_invoked:
        reasons.append("research_owned_client_not_executed")
    if owned_client_result.external_transport_result is None:
        reasons.append("research_owned_external_result_required")
    if owned_client_result.credential_material_accessed or owned_client_result.raw_secret_returned:
        reasons.append("research_owned_client_secret_leak_detected")
    if not owned_client_result.no_secret_echo or owned_client_result.live_production_claimed:
        reasons.append("research_owned_client_secret_leak_detected")
    if (
        external_result is not None
        and owned_client_result.external_transport_result is not None
        and external_result.execution_id != owned_client_result.external_transport_result.execution_id
    ):
        reasons.append("research_owned_external_mismatch")
    resolved = external_result if external_result is not None else owned_client_result.external_transport_result
    return resolved, tuple(dict.fromkeys(reasons))


def _input_reasons(*, safe_record_ref: Optional[str], secret_seen: bool) -> tuple[str, ...]:
    reasons: list[str] = []
    if safe_record_ref is None:
        reasons.append("execution_record_ref_required")
    if secret_seen:
        reasons.append("secret_like_external_execution_field")
    return tuple(reasons)


def _preflight_reasons(preflight: LiveResearchWorkflowExternalPreflightResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if preflight.decision != "external_preflight_ready" or not preflight.external_transport_allowed:
        reasons.append("research_workflow_external_preflight_not_ready")
    if preflight.preflight_id is None or preflight.external_execution_ref is None:
        reasons.append("research_workflow_external_preflight_identity_missing")
    if not preflight.workflow_handoff_bound or not preflight.policy_bound:
        reasons.append("research_workflow_external_preflight_controls_missing")
    if preflight.live_transport_enabled or preflight.network_opened:
        reasons.append("research_workflow_external_preflight_side_effect_detected")
    if preflight.credential_material_accessed or preflight.raw_secret_returned:
        reasons.append("research_workflow_external_preflight_secret_leak_detected")
    if not preflight.no_secret_echo or preflight.live_production_claimed:
        reasons.append("research_workflow_external_preflight_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _external_reasons(
    external_result: Optional[LiveResearchExternalTransportResult],
) -> tuple[str, ...]:
    if external_result is None:
        return ("research_external_transport_result_required",)
    reasons: list[str] = []
    if external_result.decision != "executed" or not external_result.research_invoked:
        reasons.append("research_external_transport_not_executed")
    if not external_result.live_search_enabled or not external_result.execution_allowed:
        reasons.append("research_external_transport_not_allowed")
    if not external_result.source_pin_bound or not external_result.network_opened:
        reasons.append("research_external_transport_evidence_incomplete")
    if not external_result.non_loopback_network_opened:
        reasons.append("research_external_non_loopback_network_not_confirmed")
    if external_result.cleanup_receipt != _EXTERNAL_CLEANUP_RECEIPT:
        reasons.append("research_external_cleanup_receipt_invalid")
    if external_result.credential_material_accessed or external_result.raw_secret_returned:
        reasons.append("research_external_secret_leak_detected")
    if not external_result.no_secret_echo or external_result.live_production_claimed:
        reasons.append("research_external_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _match_reasons(
    preflight: LiveResearchWorkflowExternalPreflightResult,
    external_result: Optional[LiveResearchExternalTransportResult],
) -> tuple[str, ...]:
    if external_result is None:
        return ()
    reasons: list[str] = []
    if external_result.policy_id != preflight.policy_id:
        reasons.append("research_external_policy_mismatch")
    if external_result.source_id != preflight.source_id:
        reasons.append("research_external_source_mismatch")
    if external_result.source_pin_ref != preflight.source_pin_ref:
        reasons.append("research_external_source_pin_mismatch")
    if external_result.execution_ref != preflight.external_execution_ref:
        reasons.append("research_external_execution_ref_mismatch")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> tuple[Optional[str], bool]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None, False
    return redacted, redacted != value.strip()


def _execution_id(
    preflight: LiveResearchWorkflowExternalPreflightResult,
    external_result: Optional[LiveResearchExternalTransportResult],
    execution_record_ref: Optional[str],
) -> str:
    payload = {
        "execution_record_ref": execution_record_ref,
        "external_transport_execution_id": (
            None if external_result is None else external_result.execution_id
        ),
        "preflight_id": preflight.preflight_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-external-execution-{0}".format(
        hashlib.sha256(encoded).hexdigest()[:16]
    )


def _recommended_next_commands(
    decision: ResearchWorkflowExternalExecutionDecision,
) -> tuple[str, ...]:
    if decision == "external_execution_recorded":
        return ("zeus live-research-evidence-graph --json", "zeus live --json")
    return (
        "zeus live-research-workflow-external-preflight --json",
        "zeus live-research-external-transport --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowExternalExecutionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
