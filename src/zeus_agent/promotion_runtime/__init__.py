"""Earned-promotion contract (M4), shared by memory / ontology / skill / rule.

Promotion is candidate → evidence-scored → (auto only if low-risk, reversible,
and golden-set-passing | else human review) → promoted with a rollback token.
Hard-risk candidates can NEVER auto-promote — human review always. This is the
single place that turns "self-improvement" into earned change, not drift.
"""

from __future__ import annotations

from .review import (
    PromotionCandidate,
    PromotionDecision,
    PromotionKind,
    review_promotion,
)

__all__ = [
    "PromotionCandidate",
    "PromotionDecision",
    "PromotionKind",
    "review_promotion",
]
