from __future__ import annotations

from typing import Optional

from pydantic import JsonValue

from zeus_agent.live_research_status_runtime import LiveResearchStatusResult
from zeus_agent.live_research_workflow_authorization_runtime import LiveResearchWorkflowAuthorizationResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseResult,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorResult,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusResult,
)
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryResult,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightResult,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionResult,
)
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryResult,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanResult
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewResult
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookResult
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowResult


def research_summary(
    *,
    research_status: Optional[LiveResearchStatusResult],
    research_workflow: Optional[LiveResearchWorkflowResult],
    bundle_status: Optional[LiveResearchWorkflowBundleStatusResult],
    bundle_review: Optional[LiveResearchWorkflowBundleReviewResult],
    runbook: Optional[LiveResearchWorkflowRunbookResult],
    preflight_plan: Optional[LiveResearchWorkflowPreflightPlanResult],
    authorization: Optional[LiveResearchWorkflowAuthorizationResult],
    executor_release: Optional[LiveResearchWorkflowExecutorReleaseResult],
    execution_handoff: Optional[LiveResearchWorkflowExecutionHandoffResult],
    loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    execution_status: Optional[LiveResearchWorkflowExecutionStatusResult],
    execution_registry: Optional[LiveResearchWorkflowExecutionRegistryResult],
    external_preflight: Optional[LiveResearchWorkflowExternalPreflightResult],
    external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
    ontology_ingestion: Optional[LiveResearchWorkflowOntologyIngestionResult],
    ontology_registry: Optional[LiveResearchWorkflowOntologyRegistryResult],
) -> dict[str, JsonValue]:
    return {
        "research_status_decision": None if research_status is None else research_status.decision,
        "research_chain_recorded": research_status is not None and research_status.decision == "recorded",
        "research_external_network_seen": False if research_status is None else research_status.external_network_seen,
        "research_workflow_decision": None if research_workflow is None else research_workflow.decision,
        "research_workflow_ready_source_count": _workflow_ready_count(research_workflow),
        "research_workflow_endpoint_required_count": _workflow_endpoint_count(research_workflow),
        "research_workflow_bundle_decision": None if bundle_status is None else bundle_status.decision,
        "research_workflow_bundle_source_plan_count": 0 if bundle_status is None else bundle_status.source_plan_count,
        "research_workflow_bundle_planned_source_count": 0 if bundle_status is None else bundle_status.planned_source_count,
        "research_workflow_bundle_endpoint_required_count": 0 if bundle_status is None else bundle_status.endpoint_required_count,
        "research_workflow_bundle_blocked_source_count": 0 if bundle_status is None else bundle_status.blocked_source_count,
        "research_workflow_bundle_review_decision": None if bundle_review is None else bundle_review.decision,
        "research_workflow_bundle_review_source_count": 0 if bundle_review is None else bundle_review.source_review_count,
        "research_workflow_bundle_review_ready_source_count": 0 if bundle_review is None else bundle_review.review_ready_source_count,
        "research_workflow_bundle_review_endpoint_required_count": 0 if bundle_review is None else bundle_review.endpoint_required_count,
        "research_workflow_bundle_review_external_required_count": 0 if bundle_review is None else bundle_review.external_review_required_count,
        "research_workflow_bundle_review_required_action_count": _review_action_count(bundle_review),
        "research_workflow_runbook_decision": None if runbook is None else runbook.decision,
        "research_workflow_runbook_step_count": 0 if runbook is None else runbook.step_count,
        "research_workflow_runbook_blocked_reason_count": _blocked_reason_count(runbook),
        "research_workflow_preflight_plan_decision": None if preflight_plan is None else preflight_plan.decision,
        "research_workflow_preflight_candidate_count": 0 if preflight_plan is None else preflight_plan.preflight_candidate_count,
        "research_workflow_preflight_required_operator_action_count": _required_operator_action_count(preflight_plan),
        "research_workflow_authorization_decision": None if authorization is None else authorization.decision,
        "research_workflow_authorization_ready": authorization is not None and authorization.decision == "authorization_ready",
        "research_workflow_authorized_candidate_count": 0 if authorization is None else authorization.authorized_candidate_count,
        "research_workflow_authorization_executor_release_granted": _authorization_release_granted(authorization),
        "research_workflow_authorization_execution_allowed": _authorization_execution_allowed(authorization),
        "research_workflow_executor_release_decision": None if executor_release is None else executor_release.decision,
        "research_workflow_executor_release_ready": executor_release is not None and executor_release.decision == "release_ready",
        "research_workflow_executor_release_granted": _executor_release_granted(executor_release),
        "research_workflow_executor_release_execution_allowed": _executor_release_allowed(executor_release),
        "research_workflow_execution_handoff_decision": None if execution_handoff is None else execution_handoff.decision,
        "research_workflow_execution_handoff_ready": execution_handoff is not None and execution_handoff.decision == "handoff_ready",
        "research_workflow_execution_handoff_manifest_id": None if execution_handoff is None else execution_handoff.manifest_id,
        "research_workflow_execution_handoff_execution_allowed": _handoff_execution_allowed(execution_handoff),
        "research_workflow_execution_handoff_live_transport_enabled": _handoff_transport_enabled(execution_handoff),
        "research_workflow_loopback_executor_decision": None if loopback_executor is None else loopback_executor.decision,
        "research_workflow_loopback_executor_ready": loopback_executor is not None and loopback_executor.decision == "loopback_executed",
        "research_workflow_loopback_executor_workflow_execution_id": None if loopback_executor is None else loopback_executor.workflow_execution_id,
        "research_workflow_loopback_executor_result_count": _executor_result_count(loopback_executor),
        "research_workflow_loopback_executor_live_transport_enabled": _loopback_transport_enabled(loopback_executor),
        "research_workflow_loopback_executor_non_loopback_network_opened": _loopback_non_loopback_seen(loopback_executor),
        "research_workflow_execution_status_decision": None if execution_status is None else execution_status.decision,
        "research_workflow_execution_status_ready": execution_status is not None and execution_status.decision == "execution_recorded",
        "research_workflow_execution_status_status_id": None if execution_status is None else execution_status.status_id,
        "research_workflow_execution_status_workflow_execution_id": None if execution_status is None else execution_status.workflow_execution_id,
        "research_workflow_execution_status_evidence_bound": _status_evidence_bound(execution_status),
        "research_workflow_execution_status_loopback_network_seen": _status_loopback_seen(execution_status),
        "research_workflow_execution_status_external_network_seen": _status_external_seen(execution_status),
        "research_workflow_execution_status_external_non_loopback_network_seen": _status_external_non_loopback_seen(execution_status),
        "research_workflow_execution_registry_decision": None if execution_registry is None else execution_registry.decision,
        "research_workflow_execution_registry_ready": _registry_ready(execution_registry),
        "research_workflow_execution_registry_record_count": 0 if execution_registry is None else execution_registry.record_count,
        "research_workflow_execution_registry_loopback_record_count": _registry_loopback_count(execution_registry),
        "research_workflow_execution_registry_external_record_count": _registry_external_count(execution_registry),
        "research_workflow_execution_registry_external_network_seen": _registry_external_seen(execution_registry),
        "research_workflow_execution_registry_deleted_count": 0 if execution_registry is None else execution_registry.deleted_count,
        "research_workflow_external_preflight_decision": None if external_preflight is None else external_preflight.decision,
        "research_workflow_external_preflight_ready": external_preflight is not None and external_preflight.decision == "external_preflight_ready",
        "research_workflow_external_preflight_preflight_id": None if external_preflight is None else external_preflight.preflight_id,
        "research_workflow_external_preflight_external_transport_allowed": _external_transport_allowed(external_preflight),
        "research_workflow_external_preflight_live_transport_enabled": _external_live_transport_enabled(external_preflight),
        "research_workflow_external_execution_decision": None if external_execution is None else external_execution.decision,
        "research_workflow_external_execution_ready": _external_execution_ready(external_execution),
        "research_workflow_external_execution_id": None if external_execution is None else external_execution.execution_id,
        "research_workflow_external_transport_execution_id": None if external_execution is None else external_execution.external_transport_execution_id,
        "research_workflow_external_execution_network_seen": _external_execution_network_seen(external_execution),
        "research_workflow_external_execution_non_loopback_network_seen": _external_execution_non_loopback_seen(external_execution),
        "research_workflow_external_execution_live_transport_enabled": _external_execution_live_transport_enabled(external_execution),
        "research_workflow_ontology_ingestion_decision": None if ontology_ingestion is None else ontology_ingestion.decision,
        "research_workflow_ontology_ingestion_ready": _ontology_ingestion_ready(ontology_ingestion),
        "research_workflow_ontology_ingestion_ingestion_id": None if ontology_ingestion is None else ontology_ingestion.ingestion_id,
        "research_workflow_ontology_ingestion_candidate_id": None if ontology_ingestion is None else ontology_ingestion.candidate_id,
        "research_workflow_ontology_ingestion_provenance_count": _ontology_provenance_count(ontology_ingestion),
        "research_workflow_ontology_registry_decision": None if ontology_registry is None else ontology_registry.decision,
        "research_workflow_ontology_registry_ready": _ontology_registry_ready(ontology_registry),
        "research_workflow_ontology_registry_record_id": None if ontology_registry is None else ontology_registry.record_id,
        "research_workflow_ontology_registry_candidate_id": None if ontology_registry is None else ontology_registry.candidate_id,
        "research_workflow_ontology_registry_record_count": _ontology_record_count(ontology_registry),
    }


def _workflow_ready_count(value: Optional[LiveResearchWorkflowResult]) -> int:
    return 0 if value is None else value.ready_source_count


def _workflow_endpoint_count(value: Optional[LiveResearchWorkflowResult]) -> int:
    return 0 if value is None else value.endpoint_required_count


def _review_action_count(value: Optional[LiveResearchWorkflowBundleReviewResult]) -> int:
    return 0 if value is None else len(value.required_operator_actions)


def _blocked_reason_count(value: Optional[LiveResearchWorkflowRunbookResult]) -> int:
    return 0 if value is None else len(value.blocked_reasons)


def _required_operator_action_count(value: Optional[LiveResearchWorkflowPreflightPlanResult]) -> int:
    return 0 if value is None else value.required_operator_action_count


def _authorization_release_granted(value: Optional[LiveResearchWorkflowAuthorizationResult]) -> bool:
    return False if value is None else value.executor_release_granted


def _authorization_execution_allowed(value: Optional[LiveResearchWorkflowAuthorizationResult]) -> bool:
    return False if value is None else value.execution_allowed


def _executor_release_granted(value: Optional[LiveResearchWorkflowExecutorReleaseResult]) -> bool:
    return False if value is None else value.executor_release_granted


def _executor_release_allowed(value: Optional[LiveResearchWorkflowExecutorReleaseResult]) -> bool:
    return False if value is None else value.execution_allowed


def _handoff_execution_allowed(value: Optional[LiveResearchWorkflowExecutionHandoffResult]) -> bool:
    return False if value is None else value.execution_allowed


def _handoff_transport_enabled(value: Optional[LiveResearchWorkflowExecutionHandoffResult]) -> bool:
    return False if value is None else value.live_transport_enabled


def _executor_result_count(value: Optional[LiveResearchWorkflowLoopbackExecutorResult]) -> int:
    if value is None or value.result_count is None:
        return 0
    return value.result_count


def _loopback_transport_enabled(value: Optional[LiveResearchWorkflowLoopbackExecutorResult]) -> bool:
    return False if value is None else value.live_transport_enabled


def _loopback_non_loopback_seen(value: Optional[LiveResearchWorkflowLoopbackExecutorResult]) -> bool:
    return False if value is None else value.non_loopback_network_opened


def _status_evidence_bound(value: Optional[LiveResearchWorkflowExecutionStatusResult]) -> bool:
    return False if value is None else value.evidence_bound


def _status_loopback_seen(value: Optional[LiveResearchWorkflowExecutionStatusResult]) -> bool:
    return False if value is None else value.loopback_network_seen


def _status_external_seen(value: Optional[LiveResearchWorkflowExecutionStatusResult]) -> bool:
    return False if value is None else value.external_network_seen


def _status_external_non_loopback_seen(value: Optional[LiveResearchWorkflowExecutionStatusResult]) -> bool:
    return False if value is None else value.external_non_loopback_network_seen


def _registry_ready(value: Optional[LiveResearchWorkflowExecutionRegistryResult]) -> bool:
    if value is None:
        return False
    return value.decision in {"recorded", "listed", "deleted"}


def _registry_loopback_count(value: Optional[LiveResearchWorkflowExecutionRegistryResult]) -> int:
    return 0 if value is None else value.loopback_execution_record_count


def _registry_external_count(value: Optional[LiveResearchWorkflowExecutionRegistryResult]) -> int:
    return 0 if value is None else value.external_execution_record_count


def _registry_external_seen(value: Optional[LiveResearchWorkflowExecutionRegistryResult]) -> bool:
    return False if value is None else value.external_network_seen


def _external_transport_allowed(value: Optional[LiveResearchWorkflowExternalPreflightResult]) -> bool:
    return False if value is None else value.external_transport_allowed


def _external_live_transport_enabled(value: Optional[LiveResearchWorkflowExternalPreflightResult]) -> bool:
    return False if value is None else value.live_transport_enabled


def _external_execution_ready(value: Optional[LiveResearchWorkflowExternalExecutionResult]) -> bool:
    return False if value is None else value.decision == "external_execution_recorded"


def _external_execution_network_seen(value: Optional[LiveResearchWorkflowExternalExecutionResult]) -> bool:
    return False if value is None else value.external_network_seen


def _external_execution_non_loopback_seen(value: Optional[LiveResearchWorkflowExternalExecutionResult]) -> bool:
    return False if value is None else value.external_non_loopback_network_seen


def _external_execution_live_transport_enabled(value: Optional[LiveResearchWorkflowExternalExecutionResult]) -> bool:
    return False if value is None else value.live_transport_enabled


def _ontology_ingestion_ready(value: Optional[LiveResearchWorkflowOntologyIngestionResult]) -> bool:
    return False if value is None else value.decision == "workflow_candidate_proposed"


def _ontology_provenance_count(value: Optional[LiveResearchWorkflowOntologyIngestionResult]) -> int:
    return 0 if value is None else value.provenance_count


def _ontology_registry_ready(value: Optional[LiveResearchWorkflowOntologyRegistryResult]) -> bool:
    return False if value is None else value.decision == "workflow_recorded"


def _ontology_record_count(value: Optional[LiveResearchWorkflowOntologyRegistryResult]) -> int:
    return 0 if value is None else value.record_count
