from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.live_readiness_runtime import LiveReadinessReport
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

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)


class LiveCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    profile: Literal["live"]
    readiness: LiveReadinessReport
    optin_smoke: Optional[LiveOptInSmokeResult] = None
    research_status: Optional[LiveResearchStatusResult] = None
    research_workflow: Optional[LiveResearchWorkflowResult] = None
    research_workflow_bundle_status: Optional[LiveResearchWorkflowBundleStatusResult] = None
    research_workflow_bundle_review: Optional[LiveResearchWorkflowBundleReviewResult] = None
    research_workflow_runbook: Optional[LiveResearchWorkflowRunbookResult] = None
    research_workflow_preflight_plan: Optional[LiveResearchWorkflowPreflightPlanResult] = None
    research_workflow_authorization: Optional[LiveResearchWorkflowAuthorizationResult] = None
    research_workflow_executor_release: Optional[LiveResearchWorkflowExecutorReleaseResult] = None
    research_workflow_execution_handoff: Optional[LiveResearchWorkflowExecutionHandoffResult] = None
    research_workflow_loopback_executor: Optional[LiveResearchWorkflowLoopbackExecutorResult] = None
    research_workflow_execution_status: Optional[LiveResearchWorkflowExecutionStatusResult] = None
    research_workflow_execution_registry: Optional[LiveResearchWorkflowExecutionRegistryResult] = None
    research_workflow_external_preflight: Optional[LiveResearchWorkflowExternalPreflightResult] = None
    research_workflow_external_execution: Optional[LiveResearchWorkflowExternalExecutionResult] = None
    research_workflow_ontology_ingestion: Optional[LiveResearchWorkflowOntologyIngestionResult] = None
    research_workflow_ontology_registry: Optional[LiveResearchWorkflowOntologyRegistryResult] = None
    configuration_context: dict[str, JsonValue] = Field(default_factory=dict)
    surface_count: int
    live_beta_count: int
    blocked_count: int
    approval_required: bool
    research_status_decision: Optional[str] = None
    research_chain_recorded: bool = False
    research_external_network_seen: bool = False
    research_workflow_decision: Optional[str] = None
    research_workflow_ready_source_count: int = 0
    research_workflow_endpoint_required_count: int = 0
    research_workflow_bundle_decision: Optional[str] = None
    research_workflow_bundle_source_plan_count: int = 0
    research_workflow_bundle_planned_source_count: int = 0
    research_workflow_bundle_endpoint_required_count: int = 0
    research_workflow_bundle_blocked_source_count: int = 0
    research_workflow_bundle_review_decision: Optional[str] = None
    research_workflow_bundle_review_source_count: int = 0
    research_workflow_bundle_review_ready_source_count: int = 0
    research_workflow_bundle_review_endpoint_required_count: int = 0
    research_workflow_bundle_review_external_required_count: int = 0
    research_workflow_bundle_review_required_action_count: int = 0
    research_workflow_runbook_decision: Optional[str] = None
    research_workflow_runbook_step_count: int = 0
    research_workflow_runbook_blocked_reason_count: int = 0
    research_workflow_preflight_plan_decision: Optional[str] = None
    research_workflow_preflight_candidate_count: int = 0
    research_workflow_preflight_required_operator_action_count: int = 0
    research_workflow_authorization_decision: Optional[str] = None
    research_workflow_authorization_ready: bool = False
    research_workflow_authorized_candidate_count: int = 0
    research_workflow_authorization_executor_release_granted: bool = False
    research_workflow_authorization_execution_allowed: bool = False
    research_workflow_executor_release_decision: Optional[str] = None
    research_workflow_executor_release_ready: bool = False
    research_workflow_executor_release_granted: bool = False
    research_workflow_executor_release_execution_allowed: bool = False
    research_workflow_execution_handoff_decision: Optional[str] = None
    research_workflow_execution_handoff_ready: bool = False
    research_workflow_execution_handoff_manifest_id: Optional[str] = None
    research_workflow_execution_handoff_execution_allowed: bool = False
    research_workflow_execution_handoff_live_transport_enabled: bool = False
    research_workflow_loopback_executor_decision: Optional[str] = None
    research_workflow_loopback_executor_ready: bool = False
    research_workflow_loopback_executor_workflow_execution_id: Optional[str] = None
    research_workflow_loopback_executor_result_count: int = 0
    research_workflow_loopback_executor_live_transport_enabled: bool = False
    research_workflow_loopback_executor_non_loopback_network_opened: bool = False
    research_workflow_execution_status_decision: Optional[str] = None
    research_workflow_execution_status_ready: bool = False
    research_workflow_execution_status_status_id: Optional[str] = None
    research_workflow_execution_status_workflow_execution_id: Optional[str] = None
    research_workflow_execution_status_evidence_bound: bool = False
    research_workflow_execution_status_loopback_network_seen: bool = False
    research_workflow_execution_status_external_network_seen: bool = False
    research_workflow_execution_status_external_non_loopback_network_seen: bool = False
    research_workflow_execution_registry_decision: Optional[str] = None
    research_workflow_execution_registry_ready: bool = False
    research_workflow_execution_registry_record_count: int = 0
    research_workflow_execution_registry_loopback_record_count: int = 0
    research_workflow_execution_registry_external_record_count: int = 0
    research_workflow_execution_registry_external_network_seen: bool = False
    research_workflow_execution_registry_deleted_count: int = 0
    research_workflow_external_preflight_decision: Optional[str] = None
    research_workflow_external_preflight_ready: bool = False
    research_workflow_external_preflight_preflight_id: Optional[str] = None
    research_workflow_external_preflight_external_transport_allowed: bool = False
    research_workflow_external_preflight_live_transport_enabled: bool = False
    research_workflow_external_execution_decision: Optional[str] = None
    research_workflow_external_execution_ready: bool = False
    research_workflow_external_execution_id: Optional[str] = None
    research_workflow_external_transport_execution_id: Optional[str] = None
    research_workflow_external_execution_network_seen: bool = False
    research_workflow_external_execution_non_loopback_network_seen: bool = False
    research_workflow_external_execution_live_transport_enabled: bool = False
    research_workflow_ontology_ingestion_decision: Optional[str] = None
    research_workflow_ontology_ingestion_ready: bool = False
    research_workflow_ontology_ingestion_ingestion_id: Optional[str] = None
    research_workflow_ontology_ingestion_candidate_id: Optional[str] = None
    research_workflow_ontology_ingestion_provenance_count: int = 0
    research_workflow_ontology_registry_decision: Optional[str] = None
    research_workflow_ontology_registry_ready: bool = False
    research_workflow_ontology_registry_record_id: Optional[str] = None
    research_workflow_ontology_registry_candidate_id: Optional[str] = None
    research_workflow_ontology_registry_record_count: int = 0
    activation_pipeline: tuple[dict[str, JsonValue], ...]
    activation_pipeline_count: int
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
