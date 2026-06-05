from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from zeus_agent.live_research_workflow_execution_status_runtime.models import (
    LiveResearchWorkflowExecutionStatusResult,
    ResearchWorkflowExecutionStatusDecision,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorResult,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)
from zeus_agent.security.credentials import redact_secret_spans

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowExecutionStatusRuntime:
    def build(
        self,
        *,
        loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult] = None,
        external_execution: Optional[LiveResearchWorkflowExternalExecutionResult] = None,
        status_ref: str,
        evidence_ref: str,
    ) -> LiveResearchWorkflowExecutionStatusResult:
        safe_status_ref = _safe_optional(status_ref)
        safe_evidence_ref = _safe_optional(evidence_ref)
        reasons = _blocked_reasons(
            loopback_executor=loopback_executor,
            external_execution=external_execution,
            status_ref=safe_status_ref,
            evidence_ref=safe_evidence_ref,
        )
        decision: ResearchWorkflowExecutionStatusDecision = (
            "blocked" if reasons else "execution_recorded"
        )
        result = LiveResearchWorkflowExecutionStatusResult(
            decision=decision,
            status_id=_status_id(
                loopback_executor=loopback_executor,
                external_execution=external_execution,
                status_ref=safe_status_ref,
                evidence_ref=safe_evidence_ref,
            )
            if decision == "execution_recorded"
            else None,
            status_ref=safe_status_ref or "",
            evidence_ref=safe_evidence_ref,
            workflow_execution_id=_workflow_execution_id(loopback_executor, external_execution),
            execution_kind=(
                "loopback"
                if loopback_executor is not None
                else "external" if external_execution is not None else None
            ),
            external_execution_id=None if external_execution is None else external_execution.execution_id,
            external_transport_execution_id=(
                None if external_execution is None else external_execution.external_transport_execution_id
            ),
            external_preflight_ref=None if external_execution is None else external_execution.preflight_ref,
            handoff_manifest_id=_handoff_manifest_id(loopback_executor, external_execution),
            handoff_ref=None if loopback_executor is None else loopback_executor.handoff_ref,
            adapter_id=None if loopback_executor is None else loopback_executor.adapter_id,
            source_id=_source_id(loopback_executor, external_execution),
            result_count=_result_count(loopback_executor, external_execution),
            blocked_reasons=reasons,
            loopback_executor_bound=decision == "execution_recorded" and loopback_executor is not None,
            external_execution_bound=decision == "execution_recorded" and external_execution is not None,
            evidence_bound=safe_evidence_ref is not None,
            loopback_network_seen=False if loopback_executor is None else loopback_executor.network_opened,
            external_network_seen=False if external_execution is None else external_execution.external_network_seen,
            external_non_loopback_network_seen=(
                False if external_execution is None else external_execution.external_non_loopback_network_seen
            ),
            non_loopback_network_opened=False if loopback_executor is None else loopback_executor.non_loopback_network_opened,
            production_ready=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=(
                loopback_executor.raw_secret_returned
                if loopback_executor is not None
                else False if external_execution is None else external_execution.raw_secret_returned
            ),
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _blocked_reasons(
    *,
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
    status_ref: Optional[str],
    evidence_ref: Optional[str],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if status_ref is None:
        reasons.append("status_ref_required")
    if evidence_ref is None:
        reasons.append("evidence_ref_required")
    if loopback_executor is None and external_execution is None:
        reasons.append("research_workflow_execution_source_required")
    if loopback_executor is not None and external_execution is not None:
        reasons.append("research_workflow_execution_source_ambiguous")
    reasons.extend(_loopback_reasons(loopback_executor))
    reasons.extend(_external_reasons(external_execution))
    return tuple(dict.fromkeys(reasons))


def _loopback_reasons(
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
) -> tuple[str, ...]:
    if loopback_executor is None:
        return ()
    reasons: list[str] = []
    if loopback_executor.decision != "loopback_executed":
        reasons.append("research_workflow_loopback_executor_not_executed")
    if loopback_executor.non_loopback_network_opened:
        reasons.append("research_workflow_execution_status_non_loopback_opened")
    if loopback_executor.credential_material_accessed or loopback_executor.raw_secret_returned:
        reasons.append("research_workflow_execution_status_secret_leak_detected")
    if not loopback_executor.no_secret_echo:
        reasons.append("research_workflow_execution_status_secret_echo")
    if loopback_executor.live_production_claimed:
        reasons.append("research_workflow_execution_status_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _external_reasons(
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
) -> tuple[str, ...]:
    if external_execution is None:
        return ()
    reasons: list[str] = []
    if external_execution.decision != "external_execution_recorded":
        reasons.append("research_workflow_external_execution_not_recorded")
    if external_execution.execution_id is None:
        reasons.append("research_workflow_external_execution_identity_missing")
    if not external_execution.external_result_bound or not external_execution.external_transport_executed:
        reasons.append("research_workflow_external_execution_transport_missing")
    if not external_execution.external_cleanup_receipt_bound:
        reasons.append("research_workflow_external_execution_cleanup_missing")
    if external_execution.network_opened or external_execution.live_transport_enabled:
        reasons.append("research_workflow_external_execution_status_side_effect_detected")
    if external_execution.credential_material_accessed or external_execution.raw_secret_returned:
        reasons.append("research_workflow_external_execution_status_secret_leak_detected")
    if not external_execution.no_secret_echo:
        reasons.append("research_workflow_external_execution_status_secret_echo")
    if external_execution.live_production_claimed:
        reasons.append("research_workflow_external_execution_status_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _status_id(
    *,
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
    status_ref: Optional[str],
    evidence_ref: Optional[str],
) -> str:
    payload = {
        "evidence_ref": evidence_ref,
        "status_ref": status_ref,
        "workflow_execution_id": _workflow_execution_id(loopback_executor, external_execution),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-execution-status-{0}".format(
        hashlib.sha256(encoded).hexdigest()[:16]
    )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _workflow_execution_id(
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
) -> Optional[str]:
    if loopback_executor is not None:
        return loopback_executor.workflow_execution_id
    return None if external_execution is None else external_execution.execution_id


def _handoff_manifest_id(
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
) -> Optional[str]:
    if loopback_executor is not None:
        return loopback_executor.handoff_manifest_id
    return None if external_execution is None else external_execution.handoff_manifest_id


def _source_id(
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
) -> Optional[str]:
    if loopback_executor is not None:
        return loopback_executor.source_id
    return None if external_execution is None else external_execution.source_id


def _result_count(
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
) -> int:
    if loopback_executor is not None:
        return 0 if loopback_executor.result_count is None else loopback_executor.result_count
    if external_execution is None or external_execution.result_count is None:
        return 0
    return external_execution.result_count




def _recommended_next_commands(
    decision: ResearchWorkflowExecutionStatusDecision,
) -> tuple[str, ...]:
    if decision == "execution_recorded":
        return (
            "zeus live --json",
            "zeus live-research-workflow-execution-record --json",
        )
    return (
        "zeus live-research-workflow-loopback-executor --json",
        "zeus live-research-workflow-execution-status --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowExecutionStatusResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
