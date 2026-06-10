"""Gate 0 — Claude Code PreToolUse/PostToolUse hook adapter (P2).

The first real-traffic gate: every tool call in a Claude Code session flows
through ``decide()``; outcomes flow back through ``record()``; coverage and
asks/week accrue in the flight recorder from day one.
"""

from __future__ import annotations

from .card import can_explain, render_card, what_template_for
from .gate import ClaudeCodeGate, run_hook_event
from .mapping import MappedCall, map_tool_call, seed_capability_store
from .state import ControlPlaneState

__all__ = [
    "ClaudeCodeGate",
    "ControlPlaneState",
    "MappedCall",
    "can_explain",
    "map_tool_call",
    "render_card",
    "run_hook_event",
    "seed_capability_store",
    "what_template_for",
]
