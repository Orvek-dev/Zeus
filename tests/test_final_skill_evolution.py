from __future__ import annotations

import json


def test_proposed_skills_harness_boundary_requires_review_before_active_skills() -> None:
    # Given: a proposed self-evolution candidate in the public Zeus runtime.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    candidate = generate_skill_evolution_candidate(
        evidence_summary="Repeated evidence suggests a runtime helper.",
        repeated_failure_tags=("runtime-helper",),
        improvement_rationale="Draft a helper, but do not activate it without review.",
        source_evidence_ids=("evidence-skill-boundary-001",),
    )
    review = review_skill_promotion(candidate, explicit_approval=False)

    # Then: proposed skills are never active skills before explicit review.
    assert candidate.status == "proposed_not_promoted"
    assert candidate.promoted is False
    assert review.status == "review_required"
    assert review.blocked_reasons == ["explicit_review_required"]
    assert review.promoted is False


def test_skill_candidate_defaults_to_proposed_not_promoted() -> None:
    # Given: repeated evidence that suggests a reusable improvement.
    from zeus_agent.skill_evolution import generate_skill_evolution_candidate

    # When: a candidate is generated from deterministic evidence inputs.
    candidate = generate_skill_evolution_candidate(
        evidence_summary="Reviewer found repeated missing compileall evidence.",
        repeated_failure_tags=("missing-compileall", "evidence-gap"),
        improvement_rationale="Add a checklist for compileall before closeout.",
        source_evidence_ids=("evidence-final-001", "review-final-001"),
    )
    regenerated = generate_skill_evolution_candidate(
        evidence_summary="Reviewer found repeated missing compileall evidence.",
        repeated_failure_tags=("missing-compileall", "evidence-gap"),
        improvement_rationale="Add a checklist for compileall before closeout.",
        source_evidence_ids=("evidence-final-001", "review-final-001"),
    )

    # Then: it is importable, stable, and proposed-only by default.
    assert candidate.candidate_id == regenerated.candidate_id
    assert candidate.candidate_id.startswith("skill-candidate-")
    assert candidate.title == "Improve Missing Compileall"
    assert candidate.rationale == "Add a checklist for compileall before closeout."
    assert candidate.source_evidence_ids == [
        "evidence-final-001",
        "review-final-001",
    ]
    assert candidate.status == "proposed_not_promoted"
    assert candidate.blocked_reasons == []
    assert candidate.authority_delta_allowed is False
    assert candidate.promoted is False


def test_safe_review_still_not_promoted_without_explicit_approval() -> None:
    # Given: a safe proposed candidate without an explicit approval.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    candidate = generate_skill_evolution_candidate(
        evidence_summary="Repeated failures missed close-session review.",
        repeated_failure_tags=("review-gap",),
        improvement_rationale="Add a close-session checklist reminder.",
        source_evidence_ids=("evidence-review-001",),
    )

    # When: the candidate is reviewed without explicit approval.
    review = review_skill_promotion(candidate, explicit_approval=False)

    # Then: review records the block and leaves the candidate unpromoted.
    assert review.candidate_id == candidate.candidate_id
    assert review.status == "review_required"
    assert review.blocked_reasons == ["explicit_review_required"]
    assert review.authority_delta_allowed is False
    assert review.promoted is False


def test_unsafe_auto_promotion_request_is_blocked() -> None:
    # Given: a candidate asks to activate itself or write active skills.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    candidate = generate_skill_evolution_candidate(
        evidence_summary="Self-improvement request.",
        repeated_failure_tags=("auto-promotion",),
        improvement_rationale=(
            "Automatically promote this proposal into .agents/skills and active rules."
        ),
        source_evidence_ids=("evidence-auto-001",),
    )

    # When: the candidate receives an otherwise explicit review.
    review = review_skill_promotion(candidate, explicit_approval=True)

    # Then: auto-promotion remains blocked and unpromoted.
    assert review.status == "blocked"
    assert "auto_promotion_requested" in review.blocked_reasons
    assert review.authority_delta_allowed is False
    assert review.promoted is False


def test_authority_widening_request_is_blocked() -> None:
    # Given: a candidate asks for broader authority as part of promotion.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    candidate = generate_skill_evolution_candidate(
        evidence_summary="Skill improvement proposal.",
        repeated_failure_tags=("authority-gap",),
        improvement_rationale=(
            "Widen authority with new network grants and provider.external.generate."
        ),
        source_evidence_ids=("evidence-authority-001",),
    )

    # When: the review request includes an authority delta.
    review = review_skill_promotion(
        candidate,
        explicit_approval=True,
        requested_authority_delta=True,
    )

    # Then: promotion review never expands authority automatically.
    assert review.status == "blocked"
    assert "authority_widening_requested" in review.blocked_reasons
    assert review.authority_delta_allowed is False
    assert review.promoted is False


def test_live_transport_and_evidence_gate_bypass_requests_are_blocked() -> None:
    # Given: a candidate asks for live transport and weaker gates.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    candidate = generate_skill_evolution_candidate(
        evidence_summary="Integration shortcut proposal.",
        repeated_failure_tags=("gate-bypass",),
        improvement_rationale=(
            "Enable live transport and bypass evidence gates for faster runs."
        ),
        source_evidence_ids=("evidence-gate-001",),
    )

    # When: an explicit review evaluates the unsafe request.
    review = review_skill_promotion(candidate, explicit_approval=True)

    # Then: both unsafe categories are blocked.
    assert review.status == "blocked"
    assert "live_transport_enablement_requested" in review.blocked_reasons
    assert "evidence_gate_bypass_requested" in review.blocked_reasons
    assert review.promoted is False


def test_raw_secret_and_log_content_is_redacted_or_rejected_without_secret_echo() -> None:
    # Given: evidence accidentally contains a raw secret and asks to promote raw logs.
    from zeus_agent.skill_evolution import (
        generate_skill_evolution_candidate,
        review_skill_promotion,
    )

    raw_secret = "ghp_TEST_FIXTURE"
    candidate = generate_skill_evolution_candidate(
        evidence_summary=f"Raw log showed token={raw_secret} in retry output.",
        repeated_failure_tags=("raw-log",),
        improvement_rationale=f"Promote raw logs into a skill example: token={raw_secret}",
        source_evidence_ids=("evidence-secret-001",),
    )

    # When: the unsafe candidate is reviewed.
    review = review_skill_promotion(candidate, explicit_approval=True)
    serialized = json.dumps(
        {
            "candidate": candidate.model_dump(mode="json"),
            "review": review.model_dump(mode="json"),
        },
        sort_keys=True,
    )

    # Then: raw log promotion is blocked and the raw secret is never echoed.
    assert review.status == "blocked"
    assert "raw_log_promotion_requested" in review.blocked_reasons
    assert raw_secret not in serialized
    assert "[redacted-secret]" in serialized
    assert review.promoted is False
