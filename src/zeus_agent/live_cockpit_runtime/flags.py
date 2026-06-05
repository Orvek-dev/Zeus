from __future__ import annotations

from typing import Optional

from zeus_agent.live_readiness_runtime import LiveReadinessReport
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
from zeus_agent.live_smoke_runtime import LiveOptInSmokeResult


def network_opened(
    readiness: LiveReadinessReport,
    smoke: Optional[LiveOptInSmokeResult],
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
) -> bool:
    return (
        readiness.network_opened
        or (smoke.network_opened if smoke is not None else False)
        or (bundle_status.network_opened if bundle_status is not None else False)
        or (bundle_review.network_opened if bundle_review is not None else False)
        or (runbook.network_opened if runbook is not None else False)
        or (preflight_plan.network_opened if preflight_plan is not None else False)
        or (authorization.network_opened if authorization is not None else False)
        or (executor_release.network_opened if executor_release is not None else False)
        or (execution_handoff.network_opened if execution_handoff is not None else False)
        or (loopback_executor.network_opened if loopback_executor is not None else False)
        or (execution_status.network_opened if execution_status is not None else False)
        or (execution_registry.network_opened if execution_registry is not None else False)
        or (external_preflight.network_opened if external_preflight is not None else False)
        or (external_execution.network_opened if external_execution is not None else False)
        or (ontology_ingestion.network_opened if ontology_ingestion is not None else False)
        or (ontology_registry.network_opened if ontology_registry is not None else False)
    )


def handler_executed(readiness: LiveReadinessReport, smoke: Optional[LiveOptInSmokeResult]) -> bool:
    return readiness.handler_executed or (smoke.handler_executed if smoke is not None else False)


def external_delivery_opened(readiness: LiveReadinessReport, smoke: Optional[LiveOptInSmokeResult]) -> bool:
    return readiness.external_delivery_opened or (
        smoke.external_delivery_opened if smoke is not None else False
    )


def credential_material_accessed(
    readiness: LiveReadinessReport,
    smoke: Optional[LiveOptInSmokeResult],
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
) -> bool:
    return (
        readiness.credential_material_accessed
        or (smoke.credential_material_accessed if smoke is not None else False)
        or (bundle_status.credential_material_accessed if bundle_status is not None else False)
        or (bundle_review.credential_material_accessed if bundle_review is not None else False)
        or (runbook.credential_material_accessed if runbook is not None else False)
        or (preflight_plan.credential_material_accessed if preflight_plan is not None else False)
        or (authorization.credential_material_accessed if authorization is not None else False)
        or (
            executor_release.credential_material_accessed
            if executor_release is not None
            else False
        )
        or (
            execution_handoff.credential_material_accessed
            if execution_handoff is not None
            else False
        )
        or (
            loopback_executor.credential_material_accessed
            if loopback_executor is not None
            else False
        )
        or (
            execution_status.credential_material_accessed
            if execution_status is not None
            else False
        )
        or (
            execution_registry.credential_material_accessed
            if execution_registry is not None
            else False
        )
        or (
            external_preflight.credential_material_accessed
            if external_preflight is not None
            else False
        )
        or (
            external_execution.credential_material_accessed
            if external_execution is not None
            else False
        )
        or (
            ontology_ingestion.credential_material_accessed
            if ontology_ingestion is not None
            else False
        )
        or (
            ontology_registry.credential_material_accessed
            if ontology_registry is not None
            else False
        )
    )


def live_production_claimed(
    readiness: LiveReadinessReport,
    smoke: Optional[LiveOptInSmokeResult],
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
) -> bool:
    return (
        readiness.live_production_claimed
        or (smoke.live_production_claimed if smoke is not None else False)
        or (bundle_status.live_production_claimed if bundle_status is not None else False)
        or (bundle_review.live_production_claimed if bundle_review is not None else False)
        or (runbook.live_production_claimed if runbook is not None else False)
        or (preflight_plan.live_production_claimed if preflight_plan is not None else False)
        or (authorization.live_production_claimed if authorization is not None else False)
        or (executor_release.live_production_claimed if executor_release is not None else False)
        or (execution_handoff.live_production_claimed if execution_handoff is not None else False)
        or (loopback_executor.live_production_claimed if loopback_executor is not None else False)
        or (execution_status.live_production_claimed if execution_status is not None else False)
        or (execution_registry.live_production_claimed if execution_registry is not None else False)
        or (external_preflight.live_production_claimed if external_preflight is not None else False)
        or (external_execution.live_production_claimed if external_execution is not None else False)
        or (
            ontology_ingestion.live_production_claimed
            if ontology_ingestion is not None
            else False
        )
        or (
            ontology_registry.live_production_claimed
            if ontology_registry is not None
            else False
        )
    )
