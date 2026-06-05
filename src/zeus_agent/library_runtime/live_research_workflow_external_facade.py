from __future__ import annotations

from typing import Any, Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphRuntime,
)
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
    LiveResearchWorkflowExternalExecutionRuntime,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightResult,
    LiveResearchWorkflowExternalPreflightRuntime,
)
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphResult,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionResult,
    LiveResearchWorkflowOntologyIngestionRuntime,
)
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)


class LiveResearchWorkflowExternalFacadeMixin:
    def live_research_workflow_external_preflight(
        self,
        *,
        handoff: dict[str, Any],
        policy: dict[str, Any],
        preflight_ref: str,
        external_execution_ref: str,
        operator_approval_ref: str,
        evidence_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExternalPreflightRuntime().build(
            handoff=LiveResearchWorkflowExecutionHandoffResult.model_validate(handoff),
            policy=LiveResearchActivationPolicyResult.model_validate(policy),
            preflight_ref=preflight_ref,
            external_execution_ref=external_execution_ref,
            operator_approval_ref=operator_approval_ref,
            evidence_ref=evidence_ref,
        ).to_payload()

    def live_research_workflow_external_execution(
        self,
        *,
        preflight: dict[str, Any],
        external_result: Optional[dict[str, Any]] = None,
        owned_client_result: Optional[dict[str, Any]] = None,
        execution_record_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowExternalExecutionRuntime().record(
            preflight=LiveResearchWorkflowExternalPreflightResult.model_validate(preflight),
            external_result=(
                None
                if external_result is None
                else LiveResearchExternalTransportResult.model_validate(external_result)
            ),
            owned_client_result=(
                None
                if owned_client_result is None
                else LiveResearchOwnedClientTransportResult.model_validate(owned_client_result)
            ),
            execution_record_ref=execution_record_ref,
        ).to_payload()

    def live_research_workflow_evidence_graph(
        self,
        *,
        workflow_external_execution: dict[str, Any],
        external_result: dict[str, Any],
        graph_ref: str,
        objective_id: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowEvidenceGraphRuntime().build(
            workflow_external_execution=LiveResearchWorkflowExternalExecutionResult.model_validate(
                workflow_external_execution
            ),
            external_result=LiveResearchExternalTransportResult.model_validate(external_result),
            graph_ref=graph_ref,
            objective_id=objective_id,
        ).to_payload()

    def live_research_workflow_ontology_ingestion(
        self,
        *,
        workflow_graph: dict[str, Any],
        candidate_ref: str,
        term: str,
        definition: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowOntologyIngestionRuntime().propose(
            workflow_graph=LiveResearchWorkflowEvidenceGraphResult.model_validate(workflow_graph),
            candidate_ref=candidate_ref,
            term=term,
            definition=definition,
        ).to_payload()

    def live_research_workflow_ontology_record(
        self,
        *,
        workflow_ingestion: dict[str, Any],
        record_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchWorkflowOntologyRegistryRuntime(self.home).record(
            workflow_ingestion=LiveResearchWorkflowOntologyIngestionResult.model_validate(workflow_ingestion),
            record_ref=record_ref,
        ).to_payload()
