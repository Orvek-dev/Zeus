"""Skill evaluation closed loop (M4): run → measure → golden-set gate → promote.

Turns "self-evolution" from static scoring into a real loop: a skill candidate is
run against golden cases, its pass rate measured, and promotion gated on the
golden set (the Goodhart guard — a skill that games a metric but fails golden
cases cannot promote). The skill runner is injected, so the loop is deterministic
in tests and sandbox-backed in production.
"""

from __future__ import annotations

from .loop import SkillEvalReport, SkillRunResult, evaluate_skill

__all__ = ["SkillEvalReport", "SkillRunResult", "evaluate_skill"]
