from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from zeus_agent.live_cockpit_runtime.blocking import blocked_reasons as build_blocked_reasons
from zeus_agent.live_cockpit_runtime.flags import credential_material_accessed as aggregate_credential_material_accessed
from zeus_agent.live_cockpit_runtime.flags import external_delivery_opened as aggregate_external_delivery_opened
from zeus_agent.live_cockpit_runtime.flags import handler_executed as aggregate_handler_executed
from zeus_agent.live_cockpit_runtime.flags import live_production_claimed as aggregate_live_production_claimed
from zeus_agent.live_cockpit_runtime.flags import network_opened as aggregate_network_opened
from zeus_agent.live_cockpit_runtime.models import LiveCockpitResult
from zeus_agent.live_cockpit_runtime.recommendations import activation_pipeline
from zeus_agent.live_cockpit_runtime.recommendations import recommended_next_commands
from zeus_agent.live_cockpit_runtime.summaries import research_summary
from zeus_agent.live_profile_runtime import build_live_configuration_context
from zeus_agent.live_readiness_runtime import LiveReadinessRuntime
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
from zeus_agent.live_smoke_runtime import LiveOptInSmokeScenario, run_live_optin_smoke

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveCockpitRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def build(
        self,
        *,
        include_smoke: bool = False,
        scenario: LiveOptInSmokeScenario = "happy",
        research_status: Optional[LiveResearchStatusResult] = None,
        research_workflow: Optional[LiveResearchWorkflowResult] = None,
        research_workflow_bundle_status: Optional[LiveResearchWorkflowBundleStatusResult] = None,
        research_workflow_bundle_review: Optional[LiveResearchWorkflowBundleReviewResult] = None,
        research_workflow_runbook: Optional[LiveResearchWorkflowRunbookResult] = None,
        research_workflow_preflight_plan: Optional[LiveResearchWorkflowPreflightPlanResult] = None,
        research_workflow_authorization: Optional[LiveResearchWorkflowAuthorizationResult] = None,
        research_workflow_executor_release: Optional[LiveResearchWorkflowExecutorReleaseResult] = None,
        research_workflow_execution_handoff: Optional[LiveResearchWorkflowExecutionHandoffResult] = None,
        research_workflow_loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult] = None,
        research_workflow_execution_status: Optional[LiveResearchWorkflowExecutionStatusResult] = None,
        research_workflow_execution_registry: Optional[LiveResearchWorkflowExecutionRegistryResult] = None,
        research_workflow_external_preflight: Optional[LiveResearchWorkflowExternalPreflightResult] = None,
        research_workflow_external_execution: Optional[LiveResearchWorkflowExternalExecutionResult] = None,
        research_workflow_ontology_ingestion: Optional[LiveResearchWorkflowOntologyIngestionResult] = None,
        research_workflow_ontology_registry: Optional[LiveResearchWorkflowOntologyRegistryResult] = None,
    ) -> LiveCockpitResult:
        smoke = run_live_optin_smoke(scenario=scenario) if include_smoke else None
        readiness = smoke.readiness if smoke is not None else LiveReadinessRuntime().build_report()
        configuration_context = build_live_configuration_context(self.home)
        blocked_reasons = build_blocked_reasons(
            smoke,
            research_status,
            research_workflow,
            research_workflow_bundle_status,
            research_workflow_bundle_review,
            research_workflow_runbook,
            research_workflow_preflight_plan,
            research_workflow_authorization,
            research_workflow_executor_release,
            research_workflow_execution_handoff,
            research_workflow_loopback_executor,
            research_workflow_execution_status,
            research_workflow_execution_registry,
            research_workflow_external_preflight,
            research_workflow_external_execution,
            research_workflow_ontology_ingestion,
            research_workflow_ontology_registry,
        )
        decision: Literal["report", "blocked"] = "blocked" if blocked_reasons else "report"
        result = LiveCockpitResult(
            decision=decision,
            profile="live",
            readiness=readiness,
            optin_smoke=smoke,
            research_status=research_status,
            research_workflow=research_workflow,
            research_workflow_bundle_status=research_workflow_bundle_status,
            research_workflow_bundle_review=research_workflow_bundle_review,
            research_workflow_runbook=research_workflow_runbook,
            research_workflow_preflight_plan=research_workflow_preflight_plan,
            research_workflow_authorization=research_workflow_authorization,
            research_workflow_executor_release=research_workflow_executor_release,
            research_workflow_execution_handoff=research_workflow_execution_handoff,
            research_workflow_loopback_executor=research_workflow_loopback_executor,
            research_workflow_execution_status=research_workflow_execution_status,
            research_workflow_execution_registry=research_workflow_execution_registry,
            research_workflow_external_preflight=research_workflow_external_preflight,
            research_workflow_external_execution=research_workflow_external_execution,
            research_workflow_ontology_ingestion=research_workflow_ontology_ingestion,
            research_workflow_ontology_registry=research_workflow_ontology_registry,
            configuration_context=configuration_context,
            surface_count=readiness.surface_count,
            live_beta_count=readiness.live_beta_count,
            blocked_count=readiness.blocked_count,
            approval_required=readiness.user_approval_required,
            **research_summary(
                research_status=research_status,
                research_workflow=research_workflow,
                bundle_status=research_workflow_bundle_status,
                bundle_review=research_workflow_bundle_review,
                runbook=research_workflow_runbook,
                preflight_plan=research_workflow_preflight_plan,
                authorization=research_workflow_authorization,
                executor_release=research_workflow_executor_release,
                execution_handoff=research_workflow_execution_handoff,
                loopback_executor=research_workflow_loopback_executor,
                execution_status=research_workflow_execution_status,
                execution_registry=research_workflow_execution_registry,
                external_preflight=research_workflow_external_preflight,
                external_execution=research_workflow_external_execution,
                ontology_ingestion=research_workflow_ontology_ingestion,
                ontology_registry=research_workflow_ontology_registry,
            ),
            activation_pipeline=activation_pipeline(),
            activation_pipeline_count=5,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=recommended_next_commands(include_smoke=include_smoke),
            network_opened=aggregate_network_opened(
                readiness,
                smoke,
                research_workflow_bundle_status,
                research_workflow_bundle_review,
                research_workflow_runbook,
                research_workflow_preflight_plan,
                research_workflow_authorization,
                research_workflow_executor_release,
                research_workflow_execution_handoff,
                research_workflow_loopback_executor,
                research_workflow_execution_status,
                research_workflow_execution_registry,
                research_workflow_external_preflight,
                research_workflow_external_execution,
                research_workflow_ontology_ingestion,
                research_workflow_ontology_registry,
            ),
            handler_executed=aggregate_handler_executed(readiness, smoke),
            external_delivery_opened=aggregate_external_delivery_opened(readiness, smoke),
            credential_material_accessed=aggregate_credential_material_accessed(
                readiness,
                smoke,
                research_workflow_bundle_status,
                research_workflow_bundle_review,
                research_workflow_runbook,
                research_workflow_preflight_plan,
                research_workflow_authorization,
                research_workflow_executor_release,
                research_workflow_execution_handoff,
                research_workflow_loopback_executor,
                research_workflow_execution_status,
                research_workflow_execution_registry,
                research_workflow_external_preflight,
                research_workflow_external_execution,
                research_workflow_ontology_ingestion,
                research_workflow_ontology_registry,
            ),
            live_production_claimed=aggregate_live_production_claimed(
                readiness,
                smoke,
                research_workflow_bundle_status,
                research_workflow_bundle_review,
                research_workflow_runbook,
                research_workflow_preflight_plan,
                research_workflow_authorization,
                research_workflow_executor_release,
                research_workflow_execution_handoff,
                research_workflow_loopback_executor,
                research_workflow_execution_status,
                research_workflow_execution_registry,
                research_workflow_external_preflight,
                research_workflow_external_execution,
                research_workflow_ontology_ingestion,
                research_workflow_ontology_registry,
            ),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
