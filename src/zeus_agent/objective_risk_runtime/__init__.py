"""Domain-independent objective risk classification and value-of-information.

This package turns a list of extracted unknowns into deterministic
question / assume / learn-by-sample / defer decisions. Domain knowledge lives in
the cognitive layer (which fills the unknown fields) and the capability
registry — never here. Zeus owns only the structure: six risk classes, the VoI
arithmetic, fail-closed hard rules, and cross-class escalations.
"""

from __future__ import annotations

from .engine import assess_objective_risk
from .models import (
    BlastRadius,
    Irreversibility,
    ObjectiveRiskProfile,
    Resolution,
    RiskClass,
    RiskContext,
    SafeDefault,
    Triage,
    Unknown,
    UnknownResolution,
)
from .voi import impact, threshold_for, voi_score

__all__ = [
    "BlastRadius",
    "Irreversibility",
    "ObjectiveRiskProfile",
    "Resolution",
    "RiskClass",
    "RiskContext",
    "SafeDefault",
    "Triage",
    "Unknown",
    "UnknownResolution",
    "assess_objective_risk",
    "impact",
    "threshold_for",
    "voi_score",
]
