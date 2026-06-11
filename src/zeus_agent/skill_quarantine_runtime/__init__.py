"""Skill supply-chain quarantine (P10, default-OFF) — was "skill evolution"/
Prometheus, re-aimed.

Honest framing: this is eval-record + gated promotion, NOT self-improvement.
As governance it is exactly what plugin/skill installs need: every install is
hash-pinned and quarantined, activation is an operator review, and a changed
manifest re-quarantines (the same rug-pull defense as MCP tools).
"""

from __future__ import annotations

from .quarantine import SkillQuarantine, SkillRecord

__all__ = ["SkillQuarantine", "SkillRecord"]
