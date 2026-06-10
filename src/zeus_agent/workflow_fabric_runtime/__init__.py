"""Governed workflow fabric: static verification and candidate selection.

Turns LLM-proposed workflow DAGs into governed plans. The crown-jewel check is
approval dominance: a side-effecting node is rejected unless an approval gate
dominates it on every path. This enforces "no irreversible action without a
preceding gate" as a graph property, with zero domain knowledge — an LLM cannot
propose its way around it.
"""

from __future__ import annotations

from .models import (
    CandidateVerdict,
    DecisionRecord,
    NodeKind,
    VerificationFinding,
    WorkflowCandidate,
    WorkflowEdge,
    WorkflowNode,
)
from .select import choose_workflow
from .verify import verify_candidate

__all__ = [
    "CandidateVerdict",
    "DecisionRecord",
    "NodeKind",
    "VerificationFinding",
    "WorkflowCandidate",
    "WorkflowEdge",
    "WorkflowNode",
    "choose_workflow",
    "verify_candidate",
]
