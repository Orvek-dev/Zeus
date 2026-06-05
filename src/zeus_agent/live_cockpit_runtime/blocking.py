from __future__ import annotations

from typing import Optional

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
from zeus_agent.live_smoke_runtime import LiveOptInSmokeResult


def blocked_reasons(
    smoke: Optional[LiveOptInSmokeResult],
    research_status: Optional[LiveResearchStatusResult],
    research_workflow: Optional[LiveResearchWorkflowResult],
    research_workflow_bundle_status: Optional[LiveResearchWorkflowBundleStatusResult],
    research_workflow_bundle_review: Optional[LiveResearchWorkflowBundleReviewResult],
    research_workflow_runbook: Optional[LiveResearchWorkflowRunbookResult],
    research_workflow_preflight_plan: Optional[LiveResearchWorkflowPreflightPlanResult],
    research_workflow_authorization: Optional[LiveResearchWorkflowAuthorizationResult],
    research_workflow_executor_release: Optional[LiveResearchWorkflowExecutorReleaseResult],
    research_workflow_execution_handoff: Optional[LiveResearchWorkflowExecutionHandoffResult],
    research_workflow_loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult],
    research_workflow_execution_status: Optional[LiveResearchWorkflowExecutionStatusResult],
    research_workflow_execution_registry: Optional[LiveResearchWorkflowExecutionRegistryResult],
    research_workflow_external_preflight: Optional[LiveResearchWorkflowExternalPreflightResult],
    research_workflow_external_execution: Optional[LiveResearchWorkflowExternalExecutionResult],
    research_workflow_ontology_ingestion: Optional[LiveResearchWorkflowOntologyIngestionResult],
    research_workflow_ontology_registry: Optional[LiveResearchWorkflowOntologyRegistryResult],
) -> tuple[str, ...]:
    reasons = [] if smoke is None else list(smoke.blocked_reasons)
    if research_status is not None and research_status.decision == "blocked":
        reasons.extend("research:{0}".format(reason) for reason in research_status.blocked_reasons)
    if research_workflow is not None and research_workflow.decision == "blocked":
        reasons.extend(
            "research-workflow:{0}".format(reason)
            for reason in research_workflow.blocked_reasons
        )
    if research_workflow_bundle_status is not None and research_workflow_bundle_status.decision == "blocked":
        reasons.extend(
            "research-workflow-bundle:{0}".format(reason)
            for reason in research_workflow_bundle_status.blocked_reasons
        )
    if research_workflow_bundle_review is not None and research_workflow_bundle_review.decision == "blocked":
        reasons.extend(
            "research-workflow-bundle-review:{0}".format(reason)
            for reason in research_workflow_bundle_review.blocked_reasons
        )
    if research_workflow_runbook is not None and research_workflow_runbook.decision == "blocked":
        reasons.extend(
            "research-workflow-runbook:{0}".format(reason)
            for reason in research_workflow_runbook.blocked_reasons
        )
    if research_workflow_preflight_plan is not None and research_workflow_preflight_plan.decision == "blocked":
        reasons.extend(
            "research-workflow-preflight-plan:{0}".format(reason)
            for reason in research_workflow_preflight_plan.blocked_reasons
        )
    if research_workflow_authorization is not None and research_workflow_authorization.decision == "blocked":
        reasons.extend(
            "research-workflow-authorization:{0}".format(reason)
            for reason in research_workflow_authorization.blocked_reasons
        )
    if research_workflow_executor_release is not None and research_workflow_executor_release.decision == "blocked":
        reasons.extend(
            "research-workflow-executor-release:{0}".format(reason)
            for reason in research_workflow_executor_release.blocked_reasons
        )
    if research_workflow_execution_handoff is not None and research_workflow_execution_handoff.decision == "blocked":
        reasons.extend(
            "research-workflow-execution-handoff:{0}".format(reason)
            for reason in research_workflow_execution_handoff.blocked_reasons
        )
    if research_workflow_loopback_executor is not None and research_workflow_loopback_executor.decision == "blocked":
        reasons.extend(
            "research-workflow-loopback-executor:{0}".format(reason)
            for reason in research_workflow_loopback_executor.blocked_reasons
        )
    if research_workflow_execution_status is not None and research_workflow_execution_status.decision == "blocked":
        reasons.extend(
            "research-workflow-execution-status:{0}".format(reason)
            for reason in research_workflow_execution_status.blocked_reasons
        )
    if research_workflow_execution_registry is not None and research_workflow_execution_registry.decision == "blocked":
        reasons.extend(
            "research-workflow-execution-registry:{0}".format(reason)
            for reason in research_workflow_execution_registry.blocked_reasons
        )
    if research_workflow_external_preflight is not None and research_workflow_external_preflight.decision == "blocked":
        reasons.extend(
            "research-workflow-external-preflight:{0}".format(reason)
            for reason in research_workflow_external_preflight.blocked_reasons
        )
    if research_workflow_external_execution is not None and research_workflow_external_execution.decision == "blocked":
        reasons.extend(
            "research-workflow-external-execution:{0}".format(reason)
            for reason in research_workflow_external_execution.blocked_reasons
        )
    if research_workflow_ontology_ingestion is not None and research_workflow_ontology_ingestion.decision == "blocked":
        reasons.extend(
            "research-workflow-ontology-ingestion:{0}".format(reason)
            for reason in research_workflow_ontology_ingestion.blocked_reasons
        )
    if research_workflow_ontology_registry is not None and research_workflow_ontology_registry.decision == "blocked":
        reasons.extend(
            "research-workflow-ontology-registry:{0}".format(reason)
            for reason in research_workflow_ontology_registry.blocked_reasons
        )
    return tuple(dict.fromkeys(reasons))
