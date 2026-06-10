"""Decision API v1 — the common contract for all four gates (P0).

``decide(DecisionRequest) -> DecisionResponse`` is decision-only: Zeus never
executes the host's tool. ``record(receipt_id, ExecutionOutcome)`` binds the
host's execution evidence back to the decision receipt, closing the causal
chain in the flight recorder.
"""

from __future__ import annotations

from .engine import ZeusDecisionEngine, conservative_record_for, derive_action_risk
from .models import (
    DecisionContext,
    DecisionRequest,
    DecisionResponse,
    GateSurface,
    HostKind,
    Obligation,
)

__all__ = [
    "DecisionContext",
    "DecisionRequest",
    "DecisionResponse",
    "GateSurface",
    "HostKind",
    "Obligation",
    "ZeusDecisionEngine",
    "conservative_record_for",
    "derive_action_risk",
]
