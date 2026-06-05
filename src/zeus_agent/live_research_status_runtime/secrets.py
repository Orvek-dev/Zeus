from __future__ import annotations

from typing import Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult


def raw_secret_returned(
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
    loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult],
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    ingestion: Optional[LiveResearchOntologyIngestionResult],
    registry_record: Optional[LiveResearchOntologyRegistryResult],
) -> bool:
    return any(
        (
            False if external_result is None else external_result.raw_secret_returned,
            False if owned_client_result is None else owned_client_result.raw_secret_returned,
            False if loopback_smoke_result is None else not loopback_smoke_result.no_secret_echo,
            False if graph_result is None else graph_result.raw_secret_returned,
            False if ingestion is None else ingestion.raw_secret_returned,
            False if registry_record is None else registry_record.raw_secret_returned,
        ),
    )


def no_secret_echo(
    policy: Optional[LiveResearchActivationPolicyResult],
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
    loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult],
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    ingestion: Optional[LiveResearchOntologyIngestionResult],
    registry_record: Optional[LiveResearchOntologyRegistryResult],
) -> bool:
    return all(
        (
            True if policy is None else policy.no_secret_echo,
            True if external_result is None else external_result.no_secret_echo,
            True if owned_client_result is None else owned_client_result.no_secret_echo,
            True if loopback_smoke_result is None else loopback_smoke_result.no_secret_echo,
            True if graph_result is None else graph_result.no_secret_echo,
            True if ingestion is None else ingestion.no_secret_echo,
            True if registry_record is None else registry_record.no_secret_echo,
        ),
    )
