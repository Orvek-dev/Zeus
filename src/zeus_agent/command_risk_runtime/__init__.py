"""Command risk classifier (M3).

Replaces the fixed terminal allowlist with a classifier that maps a shell
command to a side effect + reversibility + risk. The side effect feeds the
fabric's approval-dominance rule, so destructive commands become
approval-gated as a graph property — no special-casing in the executor.
"""

from __future__ import annotations

from .classifier import CommandRisk, classify_command

__all__ = ["CommandRisk", "classify_command"]
