from __future__ import annotations

from typing import Any, Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog_payload
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphRuntime
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanRuntime
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalClientResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportRuntime
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeRuntime
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionRuntime
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryResult
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientReceipt
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportRuntime
from zeus_agent.live_research_owned_client_transport_runtime import StaticResearchOwnedClient
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigResult
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime
from zeus_agent.library_runtime.live_status_facade import LiveStatusFacadeMixin
from zeus_agent.library_runtime.live_research_workflow_facade import LiveResearchWorkflowFacadeMixin


class LiveResearchFacadeMixin(LiveResearchWorkflowFacadeMixin, LiveStatusFacadeMixin):
    def live_research_adapters(self) -> dict[str, Any]:
        return live_research_adapter_catalog_payload()

    def live_research_source_config(
        self,
        *,
        adapter_id: str,
        endpoint: Optional[str] = None,
        allow_loopback_smoke: bool = False,
    ) -> dict[str, Any]:
        return LiveResearchSourceConfigRuntime().configure(
            adapter_id=adapter_id,
            endpoint=endpoint,
            allow_loopback_smoke=allow_loopback_smoke,
        ).to_payload()

    def live_research_execution_plan(
        self,
        *,
        source_config: dict[str, Any],
        policy: dict[str, Any],
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchExecutionPlanRuntime().plan(
            source_config=LiveResearchSourceConfigResult.model_validate(source_config),
            policy=LiveResearchActivationPolicyResult.model_validate(policy),
            execution_ref=execution_ref,
        ).to_payload()

    def live_research_loopback_smoke(self, *, plan: dict[str, Any]) -> dict[str, Any]:
        return LiveResearchLoopbackSmokeRuntime().execute(
            plan=LiveResearchExecutionPlanResult.model_validate(plan),
        ).to_payload()

    def live_research_activation_policy(
        self,
        *,
        source_id: str,
        query: str,
        live_search_requested: bool = False,
        approval_ref: Optional[str] = None,
        source_pin_ref: Optional[str] = None,
        max_results: int = 5,
        rate_limit_per_minute: int = 30,
    ) -> dict[str, Any]:
        return LiveResearchActivationPolicyRuntime().plan(
            source_id=source_id,
            query=query,
            live_search_requested=live_search_requested,
            approval_ref=approval_ref,
            source_pin_ref=source_pin_ref,
            max_results=max_results,
            rate_limit_per_minute=rate_limit_per_minute,
        ).to_payload()

    def live_research_external_transport(
        self,
        policy: dict[str, Any],
        client_result: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchExternalTransportRuntime().execute(
            policy=LiveResearchActivationPolicyResult.model_validate(policy),
            client_result=LiveResearchExternalClientResult.model_validate(client_result),
            execution_ref=execution_ref,
        ).to_payload()

    def live_research_owned_client_transport(
        self,
        policy: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchOwnedClientTransportRuntime().execute(
            policy=LiveResearchActivationPolicyResult.model_validate(policy),
            client=StaticResearchOwnedClient(LiveResearchOwnedClientReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_research_evidence_graph(
        self,
        external_result: Optional[dict[str, Any]] = None,
        *,
        owned_client_result: Optional[dict[str, Any]] = None,
        graph_ref: str,
        objective_id: str,
    ) -> dict[str, Any]:
        return LiveResearchEvidenceGraphRuntime().build(
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
            graph_ref=graph_ref,
            objective_id=objective_id,
        ).to_payload()

    def live_research_ontology_ingestion(
        self,
        graph_result: dict[str, Any],
        *,
        candidate_ref: str,
        term: str,
        definition: str,
    ) -> dict[str, Any]:
        return LiveResearchOntologyIngestionRuntime().propose(
            graph_result=LiveResearchEvidenceGraphResult.model_validate(graph_result),
            candidate_ref=candidate_ref,
            term=term,
            definition=definition,
        ).to_payload()

    def live_research_ontology_record(
        self,
        ingestion: dict[str, Any],
        *,
        record_ref: str,
    ) -> dict[str, Any]:
        return LiveResearchOntologyRegistryRuntime(self.home).record(
            ingestion=LiveResearchOntologyIngestionResult.model_validate(ingestion),
            record_ref=record_ref,
        ).to_payload()

    def live_research_ontology_records(self) -> dict[str, Any]:
        return LiveResearchOntologyRegistryRuntime(self.home).list().to_payload()

    def live_research_ontology_record_delete(self, *, record_id: str, deletion_ref: str) -> dict[str, Any]:
        return LiveResearchOntologyRegistryRuntime(self.home).delete(
            record_id=record_id,
            deletion_ref=deletion_ref,
        ).to_payload()

    def live_research_status(
        self,
        *,
        policy: dict[str, Any],
        external_result: Optional[dict[str, Any]] = None,
        owned_client_result: Optional[dict[str, Any]] = None,
        loopback_smoke_result: Optional[dict[str, Any]] = None,
        graph_result: Optional[dict[str, Any]] = None,
        ingestion: Optional[dict[str, Any]] = None,
        registry_record: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return LiveResearchStatusRuntime().build(
            policy=LiveResearchActivationPolicyResult.model_validate(policy),
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
            loopback_smoke_result=(
                None
                if loopback_smoke_result is None
                else LiveResearchLoopbackSmokeResult.model_validate(loopback_smoke_result)
            ),
            graph_result=(
                None if graph_result is None else LiveResearchEvidenceGraphResult.model_validate(graph_result)
            ),
            ingestion=None if ingestion is None else LiveResearchOntologyIngestionResult.model_validate(ingestion),
            registry_record=(
                None
                if registry_record is None
                else LiveResearchOntologyRegistryResult.model_validate(registry_record)
            ),
        ).to_payload()
