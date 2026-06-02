from __future__ import annotations

import hashlib
import json
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from zeus_agent.security.credentials import redact_secret_spans

from .provenance import OntologyProvenanceRef

OntologyTermId = str
OntologyCandidateStatus = Literal["proposed_not_promoted", "blocked", "approved_for_promotion"]


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _reject_secret_like(value: str, field_name: str) -> str:
    normalized = _require_non_empty(value, field_name)
    redacted = redact_secret_spans(normalized)
    if redacted != normalized:
        raise ValueError("candidate_contains_secret_like_content")
    return normalized


def _candidate_id(term: OntologyTerm, provenance: Sequence[OntologyProvenanceRef]) -> str:
    payload = json.dumps(
        {
            "term": term.term,
            "provenance_ids": sorted(ref.source_id for ref in provenance),
        },
        sort_keys=True,
    )
    return "ontology-candidate-{0}".format(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16])


class OntologyTerm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    term: OntologyTermId
    definition: str
    aliases: tuple[str, ...] = ()

    @field_validator("term", "definition")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _reject_secret_like(value, info.field_name)

    @field_validator("aliases", mode="before")
    @classmethod
    def _coerce_aliases(cls, value: Sequence[str]) -> Sequence[str]:
        if not value:
            return ()
        return tuple(_require_non_empty(alias, "aliases") for alias in value)

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_reject_secret_like(alias, "aliases") for alias in value)


class OntologyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    candidate_id: str
    term: OntologyTerm
    rationale: str
    provenance: tuple[OntologyProvenanceRef, ...]
    status: OntologyCandidateStatus = "proposed_not_promoted"
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)
    requested_authority_widening: bool = False
    requested_live_transport: bool = False
    requested_rule_promotion: bool = False
    requested_team_rule_promotion: bool = False
    promoted: bool = False

    @field_validator("candidate_id")
    @classmethod
    def _validate_candidate_id(cls, value: str) -> str:
        return _require_non_empty(value, "candidate_id")

    @field_validator("rationale")
    @classmethod
    def _validate_rationale(cls, value: str) -> str:
        return _reject_secret_like(value, "rationale")

    @field_validator("provenance")
    @classmethod
    def _validate_provenance(cls, value: tuple[OntologyProvenanceRef, ...]) -> tuple[OntologyProvenanceRef, ...]:
        if not value:
            raise ValueError("provenance must be non-empty")
        return value


class OntologyLearningBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    candidates: tuple[OntologyCandidate, ...]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def auto_promoted_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.promoted)

    @property
    def has_auto_promotion(self) -> bool:
        return self.auto_promoted_count > 0


class OntologyCandidateBuilder:
    def build_candidate(
        self,
        *,
        term: OntologyTerm,
        rationale: str,
        provenance: Sequence[OntologyProvenanceRef],
        requested_authority_widening: bool = False,
        requested_live_transport: bool = False,
        requested_rule_promotion: bool = False,
        requested_team_rule_promotion: bool = False,
    ) -> OntologyCandidate:
        provenance_refs = tuple(provenance)
        if not provenance_refs:
            raise ValueError("ontology_provenance_required")
        if not any(ref.is_research_or_evidence for ref in provenance_refs):
            raise ValueError("ontology_candidate_requires_research_or_evidence_provenance")
        _reject_secret_like(rationale, "rationale")

        if any(
            (
                requested_authority_widening,
                requested_live_transport,
                requested_rule_promotion,
                requested_team_rule_promotion,
            )
        ):
            blocked_reasons = []
            if requested_authority_widening:
                blocked_reasons.append("authority_widening_requested")
            if requested_live_transport:
                blocked_reasons.append("live_transport_promotion_requested")
            if requested_rule_promotion:
                blocked_reasons.append("rule_promotion_requested")
            if requested_team_rule_promotion:
                blocked_reasons.append("team_rule_promotion_requested")
            status: OntologyCandidateStatus = "blocked"
        else:
            blocked_reasons = []
            status = "proposed_not_promoted"
        return OntologyCandidate(
            candidate_id=_candidate_id(term=term, provenance=provenance_refs),
            term=term,
            rationale=rationale.strip(),
            provenance=provenance_refs,
            status=status,
            blocked_reasons=tuple(blocked_reasons),
            requested_authority_widening=requested_authority_widening,
            requested_live_transport=requested_live_transport,
            requested_rule_promotion=requested_rule_promotion,
            requested_team_rule_promotion=requested_team_rule_promotion,
            promoted=False,
        )

    def propose(
        self,
        term: str,
        definition: str,
        provenance_ids: tuple[str, ...],
        requested_authority_delta: tuple[str, ...] = (),
        requested_live_transport: bool = False,
        requested_rule_promotion: bool = False,
        requested_team_rule_promotion: bool = False,
    ) -> OntologyCandidate:
        term_model = OntologyTerm(term=term, definition=definition)
        provenance = tuple(
            OntologyProvenanceRef(
                source_id=provenance_id,
                source_type=("evidence" if provenance_id.startswith("evidence") else "research"),
            )
            for provenance_id in provenance_ids
        )
        return self.build_candidate(
            term=term_model,
            rationale="Ontology candidate from propose() convenience API.",
            provenance=provenance,
            requested_authority_widening=bool(requested_authority_delta),
            requested_live_transport=requested_live_transport,
            requested_rule_promotion=requested_rule_promotion,
            requested_team_rule_promotion=requested_team_rule_promotion,
        )
