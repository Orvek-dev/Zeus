from __future__ import annotations

from typing import Optional

from .models import CandidateVerdict, DecisionRecord, WorkflowCandidate
from .verify import verify_candidate


def choose_workflow(
    candidates: tuple[WorkflowCandidate, ...],
    *,
    required_criteria: tuple[str, ...] = (),
    budget_cap_units: Optional[int] = None,
) -> DecisionRecord:
    """Verify every candidate, then pick the best passing one.

    Selection prefers: passing over failing, no-gaps over gaps, more covered
    criteria, then lower cost. Every candidate's verdict (including rejection
    findings) is retained so the decision can be audited later.
    """
    if not candidates:
        raise ValueError("no_candidates")

    verdicts = tuple(
        verify_candidate(
            candidate,
            required_criteria=required_criteria,
            budget_cap_units=budget_cap_units,
        )
        for candidate in candidates
    )
    passing = [verdict for verdict in verdicts if verdict.ok]
    rejected = tuple(verdict.candidate_id for verdict in verdicts if not verdict.ok)

    if not passing:
        return DecisionRecord(
            chosen_candidate_id=None,
            verdicts=verdicts,
            rejected=rejected,
            reason="all_candidates_failed_verification",
        )

    chosen = sorted(passing, key=_rank, reverse=True)[0]
    reason = "chosen_clean" if not chosen.has_gaps else "chosen_with_capability_gaps"
    return DecisionRecord(
        chosen_candidate_id=chosen.candidate_id,
        verdicts=verdicts,
        rejected=rejected,
        reason=reason,
    )


def _rank(verdict: CandidateVerdict) -> tuple[int, int, int]:
    return (
        0 if verdict.has_gaps else 1,
        len(verdict.covered_criteria),
        -verdict.total_cost_units,
    )
