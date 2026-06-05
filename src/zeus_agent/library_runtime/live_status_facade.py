from __future__ import annotations

from typing import Any, Optional

from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
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


class LiveStatusFacadeMixin:
    def live_status(
        self,
        *,
        include_smoke: bool = False,
        research_status: Optional[dict[str, Any]] = None,
        research_workflow: Optional[dict[str, Any]] = None,
        research_workflow_bundle_status: Optional[dict[str, Any]] = None,
        research_workflow_bundle_review: Optional[dict[str, Any]] = None,
        research_workflow_runbook: Optional[dict[str, Any]] = None,
        research_workflow_preflight_plan: Optional[dict[str, Any]] = None,
        research_workflow_authorization: Optional[dict[str, Any]] = None,
        research_workflow_executor_release: Optional[dict[str, Any]] = None,
        research_workflow_execution_handoff: Optional[dict[str, Any]] = None,
        research_workflow_loopback_executor: Optional[dict[str, Any]] = None,
        research_workflow_execution_status: Optional[dict[str, Any]] = None,
        research_workflow_execution_registry: Optional[dict[str, Any]] = None,
        research_workflow_external_preflight: Optional[dict[str, Any]] = None,
        research_workflow_external_execution: Optional[dict[str, Any]] = None,
        research_workflow_ontology_ingestion: Optional[dict[str, Any]] = None,
        research_workflow_ontology_registry: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return LiveCockpitRuntime(home=self.home).build(
            include_smoke=include_smoke,
            research_status=(
                None if research_status is None else LiveResearchStatusResult.model_validate(research_status)
            ),
            research_workflow=(
                None
                if research_workflow is None
                else LiveResearchWorkflowResult.model_validate(research_workflow)
            ),
            research_workflow_bundle_status=(
                None
                if research_workflow_bundle_status is None
                else LiveResearchWorkflowBundleStatusResult.model_validate(research_workflow_bundle_status)
            ),
            research_workflow_bundle_review=(
                None
                if research_workflow_bundle_review is None
                else LiveResearchWorkflowBundleReviewResult.model_validate(research_workflow_bundle_review)
            ),
            research_workflow_runbook=(
                None
                if research_workflow_runbook is None
                else LiveResearchWorkflowRunbookResult.model_validate(research_workflow_runbook)
            ),
            research_workflow_preflight_plan=(
                None
                if research_workflow_preflight_plan is None
                else LiveResearchWorkflowPreflightPlanResult.model_validate(research_workflow_preflight_plan)
            ),
            research_workflow_authorization=(
                None
                if research_workflow_authorization is None
                else LiveResearchWorkflowAuthorizationResult.model_validate(research_workflow_authorization)
            ),
            research_workflow_executor_release=(
                None
                if research_workflow_executor_release is None
                else LiveResearchWorkflowExecutorReleaseResult.model_validate(
                    research_workflow_executor_release
                )
            ),
            research_workflow_execution_handoff=(
                None
                if research_workflow_execution_handoff is None
                else LiveResearchWorkflowExecutionHandoffResult.model_validate(
                    research_workflow_execution_handoff
                )
            ),
            research_workflow_loopback_executor=(
                None
                if research_workflow_loopback_executor is None
                else LiveResearchWorkflowLoopbackExecutorResult.model_validate(
                    research_workflow_loopback_executor
                )
            ),
            research_workflow_execution_status=(
                None
                if research_workflow_execution_status is None
                else LiveResearchWorkflowExecutionStatusResult.model_validate(
                    research_workflow_execution_status
                )
            ),
            research_workflow_execution_registry=(
                None
                if research_workflow_execution_registry is None
                else LiveResearchWorkflowExecutionRegistryResult.model_validate(
                    research_workflow_execution_registry
                )
            ),
            research_workflow_external_preflight=(
                None
                if research_workflow_external_preflight is None
                else LiveResearchWorkflowExternalPreflightResult.model_validate(
                    research_workflow_external_preflight
                )
            ),
            research_workflow_external_execution=(
                None
                if research_workflow_external_execution is None
                else LiveResearchWorkflowExternalExecutionResult.model_validate(
                    research_workflow_external_execution
                )
            ),
            research_workflow_ontology_ingestion=(
                None
                if research_workflow_ontology_ingestion is None
                else LiveResearchWorkflowOntologyIngestionResult.model_validate(
                    research_workflow_ontology_ingestion
                )
            ),
            research_workflow_ontology_registry=(
                None
                if research_workflow_ontology_registry is None
                else LiveResearchWorkflowOntologyRegistryResult.model_validate(
                    research_workflow_ontology_registry
                )
            ),
        ).to_payload()
