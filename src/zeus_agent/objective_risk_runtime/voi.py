from __future__ import annotations

from typing import Final

from .models import BlastRadius, Irreversibility, Triage, Unknown

# Exponential (1/3/9) weights so a "public + irreversible" combination cannot be
# averaged away by an otherwise low score — the worst pairing dominates.
_IRREVERSIBILITY_WEIGHT: Final[dict[Irreversibility, int]] = {
    Irreversibility.low: 1,
    Irreversibility.medium: 3,
    Irreversibility.high: 9,
}

_BLAST_WEIGHT: Final[dict[BlastRadius, int]] = {
    BlastRadius.local: 1,
    BlastRadius.account: 3,
    BlastRadius.public: 9,
}

# A single triage-dependent knob folds in both the interruption cost and the
# autonomy appetite for that kind of work. One-shot work tolerates wrong guesses
# (high threshold, rarely asks); standing automation does not (low threshold).
_THRESHOLD: Final[dict[Triage, float]] = {
    Triage.chat: 40.0,
    Triage.oneshot: 24.0,
    Triage.project: 12.0,
    Triage.automation: 6.0,
}


def impact(unknown: Unknown) -> int:
    """Blast-weighted, irreversibility-weighted, cost-bucketed damage of a wrong guess."""
    return (
        _IRREVERSIBILITY_WEIGHT[unknown.irreversibility]
        * _BLAST_WEIGHT[unknown.blast_radius]
        * unknown.cost_bucket
    )


def voi_score(unknown: Unknown) -> float:
    """Expected damage of assuming wrong = P(assumption wrong) x impact.

    The cognitive layer estimates ``failure_probability`` (clamped to 0..1 by the
    model); Zeus owns the deterministic impact weighting.
    """
    return round(unknown.failure_probability * impact(unknown), 4)


def threshold_for(triage: Triage) -> float:
    return _THRESHOLD[triage]
