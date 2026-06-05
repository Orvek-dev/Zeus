from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_status_runtime.secrets import no_secret_echo, raw_secret_returned

LiveResearchStatusDecision = Literal[
    "policy_ready",
    "smoke_ready",
    "external_ready",
    "graph_ready",
    "candidate_proposed",
    "recorded",
    "blocked",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchStatusResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchStatusDecision
    status_id: Optional[str]
    policy_id: Optional[str]
    external_execution_id: Optional[str]
    owned_client_execution_id: Optional[str] = None
    loopback_smoke_execution_id: Optional[str] = None
    graph_id: Optional[str]
    candidate_id: Optional[str]
    record_id: Optional[str]
    source_id: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    policy_bound: bool = False
    owned_client_result_bound: bool = False
    loopback_smoke_result_bound: bool = False
    external_result_bound: bool = False
    graph_result_bound: bool = False
    ontology_candidate_bound: bool = False
    ontology_recorded: bool = False
    loopback_network_seen: bool = False
    external_network_seen: bool = False
    production_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchStatusRuntime:
    def build(
        self,
        *,
        policy: Optional[LiveResearchActivationPolicyResult],
        external_result: Optional[LiveResearchExternalTransportResult] = None,
        owned_client_result: Optional[LiveResearchOwnedClientTransportResult] = None,
        loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult] = None,
        graph_result: Optional[LiveResearchEvidenceGraphResult] = None,
        ingestion: Optional[LiveResearchOntologyIngestionResult] = None,
        registry_record: Optional[LiveResearchOntologyRegistryResult] = None,
    ) -> LiveResearchStatusResult:
        resolved_external, owned_reasons = _resolve_external_result(external_result, owned_client_result)
        reasons = tuple(dict.fromkeys((*owned_reasons, *_status_reasons(policy, resolved_external, loopback_smoke_result, graph_result, ingestion, registry_record))))
        decision = _decision(policy, resolved_external, loopback_smoke_result, graph_result, ingestion, registry_record, reasons)
        return LiveResearchStatusResult(
            decision=decision,
            status_id=_status_id(policy, resolved_external, loopback_smoke_result, graph_result, ingestion, registry_record)
            if decision != "blocked"
            else None,
            policy_id=None if policy is None else policy.policy_id,
            external_execution_id=None if resolved_external is None else resolved_external.execution_id,
            owned_client_execution_id=None if owned_client_result is None else owned_client_result.execution_id,
            loopback_smoke_execution_id=None if loopback_smoke_result is None else loopback_smoke_result.execution_id,
            graph_id=None if graph_result is None else graph_result.graph_id,
            candidate_id=None if ingestion is None else ingestion.candidate_id,
            record_id=None if registry_record is None else registry_record.record_id,
            source_id=None if policy is None else policy.source_id,
            blocked_reasons=reasons,
            recommended_next_commands=_recommended_next_commands(decision),
            policy_bound=policy is not None,
            owned_client_result_bound=owned_client_result is not None and owned_client_result.decision == "executed",
            loopback_smoke_result_bound=loopback_smoke_result is not None and loopback_smoke_result.decision == "smoke_executed",
            external_result_bound=resolved_external is not None and resolved_external.decision == "executed",
            graph_result_bound=graph_result is not None and graph_result.decision == "graph_ready",
            ontology_candidate_bound=ingestion is not None and ingestion.decision == "candidate_proposed",
            ontology_recorded=registry_record is not None and registry_record.decision == "recorded",
            loopback_network_seen=False if loopback_smoke_result is None else loopback_smoke_result.network_opened,
            external_network_seen=False if resolved_external is None else resolved_external.network_opened,
            production_ready=False,
            network_opened=False,
            handler_executed=False,
            credential_material_accessed=False,
            raw_secret_returned=raw_secret_returned(resolved_external, owned_client_result, loopback_smoke_result, graph_result, ingestion, registry_record),
            no_secret_echo=no_secret_echo(policy, resolved_external, owned_client_result, loopback_smoke_result, graph_result, ingestion, registry_record),
            live_production_claimed=False,
        )


def _resolve_external_result(
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
) -> tuple[Optional[LiveResearchExternalTransportResult], tuple[str, ...]]:
    if owned_client_result is None:
        return external_result, ()
    reasons = []
    if owned_client_result.decision != "executed" or not owned_client_result.research_invoked:
        reasons.append("research_owned_client_not_executed")
    if owned_client_result.external_transport_result is None:
        reasons.append("research_owned_external_result_required")
    if owned_client_result.credential_material_accessed or owned_client_result.raw_secret_returned:
        reasons.append("research_owned_client_secret_leak_detected")
    if not owned_client_result.no_secret_echo or owned_client_result.live_production_claimed:
        reasons.append("research_owned_client_secret_leak_detected")
    if (
        external_result is not None
        and owned_client_result.external_transport_result is not None
        and external_result.execution_id != owned_client_result.external_transport_result.execution_id
    ):
        reasons.append("research_owned_external_mismatch")
    resolved = (
        external_result
        if external_result is not None
        else owned_client_result.external_transport_result
    )
    return resolved, tuple(dict.fromkeys(reasons))


def _status_reasons(
    policy: Optional[LiveResearchActivationPolicyResult],
    external_result: Optional[LiveResearchExternalTransportResult],
    loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult],
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    ingestion: Optional[LiveResearchOntologyIngestionResult],
    registry_record: Optional[LiveResearchOntologyRegistryResult],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if policy is None:
        reasons.append("live_research_policy_required")
    elif policy.decision == "blocked" or policy.live_production_claimed:
        reasons.append("live_research_policy_blocked")
    if external_result is not None:
        if external_result.decision != "executed":
            reasons.append("research_external_result_not_ready")
        if policy is not None and external_result.policy_id != policy.policy_id:
            reasons.append("research_policy_external_mismatch")
    if loopback_smoke_result is not None:
        if loopback_smoke_result.decision != "smoke_executed":
            reasons.append("research_loopback_smoke_not_executed")
        if policy is not None and loopback_smoke_result.source_id != policy.source_id:
            reasons.append("research_loopback_smoke_policy_mismatch")
        if loopback_smoke_result.non_loopback_network_opened or loopback_smoke_result.live_production_claimed:
            reasons.append("research_loopback_smoke_scope_violation")
    if graph_result is not None:
        if graph_result.decision != "graph_ready":
            reasons.append("research_graph_not_ready")
        if external_result is not None and graph_result.external_execution_id != external_result.execution_id:
            reasons.append("research_external_graph_mismatch")
    if ingestion is not None:
        if ingestion.decision != "candidate_proposed":
            reasons.append("ontology_candidate_not_proposed")
        if graph_result is not None and ingestion.graph_id != graph_result.graph_id:
            reasons.append("ontology_candidate_graph_mismatch")
    if registry_record is not None:
        if registry_record.decision != "recorded":
            reasons.append("ontology_record_not_recorded")
        if ingestion is not None and registry_record.candidate_id != ingestion.candidate_id:
            reasons.append("ontology_record_candidate_mismatch")
    return tuple(dict.fromkeys(reasons))


def _decision(
    policy: Optional[LiveResearchActivationPolicyResult],
    external_result: Optional[LiveResearchExternalTransportResult],
    loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult],
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    ingestion: Optional[LiveResearchOntologyIngestionResult],
    registry_record: Optional[LiveResearchOntologyRegistryResult],
    reasons: tuple[str, ...],
) -> LiveResearchStatusDecision:
    if reasons:
        return "blocked"
    if registry_record is not None:
        return "recorded"
    if ingestion is not None:
        return "candidate_proposed"
    if graph_result is not None:
        return "graph_ready"
    if external_result is not None:
        return "external_ready"
    if loopback_smoke_result is not None:
        return "smoke_ready"
    return "policy_ready" if policy is not None else "blocked"


def _status_id(
    policy: Optional[LiveResearchActivationPolicyResult],
    external_result: Optional[LiveResearchExternalTransportResult],
    loopback_smoke_result: Optional[LiveResearchLoopbackSmokeResult],
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    ingestion: Optional[LiveResearchOntologyIngestionResult],
    registry_record: Optional[LiveResearchOntologyRegistryResult],
) -> str:
    payload = {
        "policy_id": None if policy is None else policy.policy_id,
        "external_execution_id": None if external_result is None else external_result.execution_id,
        "loopback_smoke_execution_id": None if loopback_smoke_result is None else loopback_smoke_result.execution_id,
        "graph_id": None if graph_result is None else graph_result.graph_id,
        "candidate_id": None if ingestion is None else ingestion.candidate_id,
        "record_id": None if registry_record is None else registry_record.record_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-status-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveResearchStatusDecision) -> tuple[str, ...]:
    if decision == "policy_ready":
        return ("zeus live-research-external-transport --json",)
    if decision == "smoke_ready":
        return ("zeus live-research-source-config --json", "zeus live-research-execution-plan --json")
    if decision == "external_ready":
        return ("zeus live-research-evidence-graph --json",)
    if decision == "graph_ready":
        return ("zeus live-research-ontology-ingestion --json",)
    if decision == "candidate_proposed":
        return ("zeus live-research-ontology-record --json",)
    if decision == "recorded":
        return ("zeus live-research-ontology-records --json", "zeus ontology --json")
    return ("zeus live-research-activation-policy --json",)
