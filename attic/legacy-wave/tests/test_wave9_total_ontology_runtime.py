from __future__ import annotations

import pytest

from zeus_agent.ontology_runtime import (
    OntologyCandidateBuilder,
    OntologyLearningBatch,
    OntologyProvenanceRef,
    OntologyTerm,
)


def test_ontology_candidate_requires_research_provenance_and_stays_proposed() -> None:
    builder = OntologyCandidateBuilder()
    term = OntologyTerm(
        term="causal_feedback_loop",
        definition="Pattern where output is reintroduced as later input.",
    )
    with pytest.raises(ValueError, match="research_or_evidence_provenance"):
        builder.build_candidate(
            term=term,
            rationale="Draft term from internal logs only.",
            provenance=(OntologyProvenanceRef(source_type="review", source_id="review-001"),),
        )

    candidate = builder.build_candidate(
        term=term,
        rationale="Draft term from internal review logs and internal traces.",
        provenance=(OntologyProvenanceRef(source_type="research", source_id="research-wave9-001"),),
    )

    assert candidate.status == "proposed_not_promoted"
    assert candidate.promoted is False
    assert candidate.provenance[0].source_id == "research-wave9-001"


def test_ontology_alias_secret_span_is_rejected() -> None:
    with pytest.raises(ValueError, match="secret_like_content") as exc:
        OntologyTerm(
            term="safe_term",
            definition="A safe term definition.",
            aliases=("alias", "sk-THIS_SHOULD_BE_REJECTED"),
        )

    assert "sk-this_should_be_rejected" not in str(exc.value).lower()


def test_ontology_candidate_id_is_deterministic_for_same_term_and_provenance() -> None:
    builder = OntologyCandidateBuilder()
    term = OntologyTerm(
        term="feedback_loop",
        definition="Recurring dependency from outputs to inputs.",
        aliases=("feedback", "loop"),
    )
    provenance = (
        OntologyProvenanceRef(source_type="research", source_id="paper-001"),
        OntologyProvenanceRef(source_type="evidence", source_id="evidence-001"),
    )
    a = builder.build_candidate(
        term=term,
        rationale="Observed evidence shows recurring dependency behavior.",
        provenance=provenance,
    )
    b = builder.build_candidate(
        term=term,
        rationale="Observed evidence shows recurring dependency behavior.",
        provenance=(provenance[1], provenance[0]),
    )

    assert a.candidate_id == b.candidate_id
    assert a.candidate_id.startswith("ontology-candidate-")


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"requested_authority_widening": True}, "authority_widening_requested"),
        ({"requested_live_transport": True}, "live_transport_promotion_requested"),
        ({"requested_rule_promotion": True}, "rule_promotion_requested"),
        ({"requested_team_rule_promotion": True}, "team_rule_promotion_requested"),
    ],
)
def test_ontology_candidate_blocks_unsafe_promotions(
    kwargs: dict[str, bool],
    reason: str,
) -> None:
    builder = OntologyCandidateBuilder()
    term = OntologyTerm(
        term="policy_refinement",
        definition="A candidate for safer rule selection.",
    )
    candidate = builder.build_candidate(
        term=term,
        rationale="Observed misses suggest this ontology term proposal.",
        provenance=(OntologyProvenanceRef(source_type="evidence", source_id="evidence-wave9-002"),),
        **kwargs,
    )

    assert candidate.status == "blocked"
    assert reason in candidate.blocked_reasons
    assert candidate.promoted is False


def test_ontology_learning_batch_reports_count_and_no_auto_promotion() -> None:
    builder = OntologyCandidateBuilder()
    term = OntologyTerm(
        term="bounded_context",
        definition="Explicit contract boundary for ontology terms.",
    )
    safe = builder.build_candidate(
        term=term,
        rationale="A bounded contract reduces accidental cross-domain terms.",
        provenance=(OntologyProvenanceRef(source_type="research", source_id="research-wave9-003"),),
    )
    blocked = builder.build_candidate(
        term=OntologyTerm(term="policy_override", definition="Manual rule override proposal."),
        rationale="Observed miss says this should bypass rules.",
        provenance=(OntologyProvenanceRef(source_type="evidence", source_id="evidence-wave9-004"),),
        requested_rule_promotion=True,
    )
    batch = OntologyLearningBatch(candidates=(safe, blocked))

    assert batch.candidate_count == 2
    assert batch.auto_promoted_count == 0
    assert batch.has_auto_promotion is False


def test_ontology_candidate_builder_public_propose_api_blocks_authority_delta_and_secret_spans() -> None:
    builder = OntologyCandidateBuilder()
    proposed = builder.propose(
        term="causal_feedback_loop",
        definition="Pattern where output becomes future input.",
        provenance_ids=("evidence-wave9-001", "research-wave9-002"),
        requested_authority_delta=("capability.delta",),
    )

    assert proposed.status == "blocked"
    assert proposed.provenance[0].source_type == "evidence"
    assert proposed.provenance[1].source_type == "research"
    assert "authority_widening_requested" in proposed.blocked_reasons
    assert proposed.promoted is False

    with pytest.raises(ValueError, match="secret_like_content"):
        builder.propose(
            term="leaky_term",
            definition="raw bearer sk-THIS_SHOULD_BE_REDACTED secret=blocked token=abc123",
            provenance_ids=("research-wave9-003",),
        )
