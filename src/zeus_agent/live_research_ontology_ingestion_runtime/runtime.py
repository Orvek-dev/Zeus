from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.ontology_runtime import (
    OntologyCandidate,
    OntologyCandidateBuilder,
    OntologyProvenanceRef,
    OntologyTerm,
)
from zeus_agent.security.credentials import redact_secret_spans

LiveResearchOntologyIngestionDecision = Literal["candidate_proposed", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
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


class LiveResearchOntologyIngestionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchOntologyIngestionDecision
    ingestion_id: Optional[str]
    candidate_ref: Optional[str]
    graph_id: Optional[str]
    candidate_id: Optional[str]
    term: Optional[str]
    definition: Optional[str]
    candidate_status: Optional[str]
    provenance_count: int = 0
    candidate_payload: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    graph_result_bound: bool = False
    candidate_proposed: bool = False
    promoted: bool = False
    ontology_term_promoted: bool = False
    wiki_page_update_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    requested_live_transport: bool = False
    requested_rule_promotion: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchOntologyIngestionRuntime:
    def propose(
        self,
        *,
        graph_result: Optional[LiveResearchEvidenceGraphResult],
        candidate_ref: str,
        term: str,
        definition: str,
    ) -> LiveResearchOntologyIngestionResult:
        safe_ref = _safe_optional(candidate_ref)
        safe_term = _safe_optional(term)
        safe_definition = _safe_optional(definition)
        reasons = list(_graph_reasons(graph_result))
        if safe_ref is None:
            reasons.append("candidate_ref_required")
        if safe_term is None:
            reasons.append("term_required")
        if safe_definition is None:
            reasons.append("definition_required")
        provenance = _provenance_refs(graph_result)
        if not provenance:
            reasons.append("graph_provenance_required")
        candidate = None
        if not reasons:
            candidate = _build_candidate(
                graph_result=graph_result,
                graph_ref=safe_ref,
                term=term,
                definition=definition,
                provenance=provenance,
            )
            if candidate is None:
                reasons.append("ontology_candidate_build_failed")
        if reasons:
            return _result(
                graph_result=graph_result,
                candidate_ref=safe_ref,
                term=safe_term,
                definition=safe_definition,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            graph_result=graph_result,
            candidate_ref=safe_ref,
            term=safe_term,
            definition=safe_definition,
            candidate=candidate,
            ingestion_id=_ingestion_id(graph_result, safe_ref),
            graph_result_bound=True,
            candidate_proposed=True,
        )


def _graph_reasons(graph_result: Optional[LiveResearchEvidenceGraphResult]) -> tuple[str, ...]:
    if graph_result is None:
        return ("research_graph_required",)
    reasons = []
    if graph_result.decision != "graph_ready" or not graph_result.graph_created:
        reasons.append("research_graph_not_ready")
    if graph_result.graph_payload is None:
        reasons.append("research_graph_payload_required")
    if not graph_result.no_secret_echo or graph_result.live_production_claimed:
        reasons.append("research_graph_secret_or_production_claim")
    if graph_result.credential_material_accessed or graph_result.raw_secret_returned:
        reasons.append("research_graph_secret_or_production_claim")
    return tuple(dict.fromkeys(reasons))


def _provenance_refs(
    graph_result: Optional[LiveResearchEvidenceGraphResult],
) -> tuple[OntologyProvenanceRef, ...]:
    if graph_result is None or graph_result.graph_payload is None:
        return ()
    raw_nodes = graph_result.graph_payload.get("nodes")
    if not isinstance(raw_nodes, list):
        return ()
    refs: list[OntologyProvenanceRef] = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        pin = node.get("source_pin")
        if not isinstance(pin, dict):
            continue
        provenance_id = pin.get("provenance_id")
        if isinstance(provenance_id, str) and provenance_id.strip():
            refs.append(OntologyProvenanceRef(source_type="research", source_id=provenance_id))
    return tuple(refs)


def _build_candidate(
    *,
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    graph_ref: str,
    term: str,
    definition: str,
    provenance: tuple[OntologyProvenanceRef, ...],
) -> Optional[OntologyCandidate]:
    try:
        return OntologyCandidateBuilder().build_candidate(
            term=OntologyTerm(term=term, definition=definition),
            rationale="Candidate proposed from live research graph {0}.".format(graph_ref),
            provenance=provenance,
        )
    except ValueError:
        return None


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _ingestion_id(
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    candidate_ref: Optional[str],
) -> str:
    payload = {
        "candidate_ref": candidate_ref,
        "graph_id": None if graph_result is None else graph_result.graph_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-ontology-ingestion-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    graph_result: Optional[LiveResearchEvidenceGraphResult],
    candidate_ref: Optional[str],
    term: Optional[str],
    definition: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    candidate: Optional[OntologyCandidate] = None,
    ingestion_id: Optional[str] = None,
    graph_result_bound: bool = False,
    candidate_proposed: bool = False,
) -> LiveResearchOntologyIngestionResult:
    result = LiveResearchOntologyIngestionResult(
        decision="candidate_proposed" if candidate_proposed else "blocked",
        ingestion_id=ingestion_id,
        candidate_ref=candidate_ref,
        graph_id=None if graph_result is None else graph_result.graph_id,
        candidate_id=None if candidate is None else candidate.candidate_id,
        term=term,
        definition=definition,
        candidate_status=None if candidate is None else candidate.status,
        provenance_count=0 if candidate is None else len(candidate.provenance),
        candidate_payload=None if candidate is None else candidate.model_dump(mode="json"),
        blocked_reasons=blocked_reasons,
        graph_result_bound=graph_result_bound,
        candidate_proposed=candidate_proposed,
        promoted=False,
        ontology_term_promoted=False,
        wiki_page_update_written=False,
        active_rule_written=False,
        authority_widened=False,
        requested_live_transport=False,
        requested_rule_promotion=False,
        network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveResearchOntologyIngestionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
