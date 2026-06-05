from __future__ import annotations

from typing import Any, Optional

from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewResult
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleResult
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusResult
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_authorization_runtime import LiveResearchWorkflowAuthorizationResult
from zeus_agent.live_research_workflow_authorization_runtime import LiveResearchWorkflowAuthorizationRuntime
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseResult,
    LiveResearchWorkflowExecutorReleaseRuntime,
)
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanRuntime
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanResult
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorResult,
    LiveResearchWorkflowLoopbackExecutorRuntime,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusResult,
    LiveResearchWorkflowExecutionStatusRuntime,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryRuntime,
)
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowResult
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime
from zeus_agent.library_runtime.live_research_workflow_external_facade import (
    LiveResearchWorkflowExternalFacadeMixin,
)


class LiveResearchWorkflowFacadeMixin(LiveResearchWorkflowExternalFacadeMixin):
    def live_research_workflow(
        self,
        *,
        query: str,
        objective_id: str = "live-research.objective",
        endpoint_overrides: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowRuntime().compile_workflow(
            query=query,
            objective_id=objective_id,
            endpoint_overrides=endpoint_overrides,
        ).to_payload()

    def live_research_workflow_bundle(
        self,
        *,
        workflow: dict[str, Any],
        bundle_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowBundleRuntime().build(
            workflow=LiveResearchWorkflowResult.model_validate(workflow),
            bundle_ref=bundle_ref,
        ).to_payload()

    def live_research_workflow_bundle_status(self, *, bundle: dict[str, Any]) -> dict[str, Any]:
        return LiveResearchWorkflowBundleStatusRuntime().build(
            bundle=LiveResearchWorkflowBundleResult.model_validate(bundle),
        ).to_payload()

    def live_research_workflow_bundle_review(
        self,
        *,
        bundle: dict[str, Any],
        status: dict[str, Any],
        review_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowBundleReviewRuntime().review(
            bundle=LiveResearchWorkflowBundleResult.model_validate(bundle),
            status=LiveResearchWorkflowBundleStatusResult.model_validate(status),
            review_ref=review_ref,
        ).to_payload()

    def live_research_workflow_runbook(
        self,
        *,
        review: dict[str, Any],
        runbook_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowRunbookRuntime().build(
            review=LiveResearchWorkflowBundleReviewResult.model_validate(review),
            runbook_ref=runbook_ref,
        ).to_payload()

    def live_research_workflow_preflight_plan(
        self,
        *,
        runbook: dict[str, Any],
        preflight_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowPreflightPlanRuntime().build(
            runbook=LiveResearchWorkflowRunbookResult.model_validate(runbook),
            preflight_ref=preflight_ref,
        ).to_payload()

    def live_research_workflow_authorization(
        self,
        *,
        preflight_plan: dict[str, Any],
        authorization_ref: str,
        operator_approval_ref: str,
        evidence_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowAuthorizationRuntime().authorize(
            preflight_plan=LiveResearchWorkflowPreflightPlanResult.model_validate(preflight_plan),
            authorization_ref=authorization_ref,
            operator_approval_ref=operator_approval_ref,
            evidence_ref=evidence_ref,
        ).to_payload()

    def live_research_workflow_executor_release(
        self,
        *,
        authorization: Optional[dict[str, Any]],
        release_ref: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExecutorReleaseRuntime().release(
            authorization=(
                None
                if authorization is None
                else LiveResearchWorkflowAuthorizationResult.model_validate(authorization)
            ),
            release_ref=release_ref,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_research_workflow_execution_handoff(
        self,
        *,
        preflight_plan: dict[str, Any],
        authorization: dict[str, Any],
        executor_release: dict[str, Any],
        handoff_ref: str,
        operator_note: Optional[str] = None,
        production_release_requested: bool = False,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExecutionHandoffRuntime().build(
            preflight_plan=LiveResearchWorkflowPreflightPlanResult.model_validate(preflight_plan),
            authorization=LiveResearchWorkflowAuthorizationResult.model_validate(authorization),
            executor_release=LiveResearchWorkflowExecutorReleaseResult.model_validate(executor_release),
            handoff_ref=handoff_ref,
            operator_note=operator_note,
            production_release_requested=production_release_requested,
        ).to_payload()

    def live_research_workflow_loopback_executor(
        self,
        *,
        handoff: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        return LiveResearchWorkflowLoopbackExecutorRuntime().execute(
            handoff=LiveResearchWorkflowExecutionHandoffResult.model_validate(handoff),
            plan=LiveResearchExecutionPlanResult.model_validate(plan),
        ).to_payload()

    def live_research_workflow_execution_status(
        self,
        *,
        loopback_executor: Optional[dict[str, Any]] = None,
        external_execution: Optional[dict[str, Any]] = None,
        status_ref: str,
        evidence_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExecutionStatusRuntime().build(
            loopback_executor=(
                None
                if loopback_executor is None
                else LiveResearchWorkflowLoopbackExecutorResult.model_validate(loopback_executor)
            ),
            external_execution=(
                None
                if external_execution is None
                else LiveResearchWorkflowExternalExecutionResult.model_validate(external_execution)
            ),
            status_ref=status_ref,
            evidence_ref=evidence_ref,
        ).to_payload()

    def live_research_workflow_execution_record(
        self,
        status: dict[str, Any],
        *,
        record_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExecutionRegistryRuntime(self.home).record(
            status=LiveResearchWorkflowExecutionStatusResult.model_validate(status),
            record_ref=record_ref,
        ).to_payload()

    def live_research_workflow_execution_records(self) -> dict[str, Any]:
        return LiveResearchWorkflowExecutionRegistryRuntime(self.home).list().to_payload()

    def live_research_workflow_execution_record_delete(
        self,
        *,
        record_id: str,
        deletion_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExecutionRegistryRuntime(self.home).delete(
            record_id=record_id,
            deletion_ref=deletion_ref,
        ).to_payload()
