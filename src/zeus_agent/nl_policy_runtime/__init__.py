"""NL policy editing (P6) — a deterministic grammar, not an LLM.

"하루 메일 5건" → a concrete governor-rule diff the human confirms. Zeus is a
brainless referee by design: anything outside the grammar is rejected with
the supported forms, never guessed.
"""

from __future__ import annotations

from .parser import RuleDiff, apply_rule_diff, parse_nl_rule, supported_grammar

__all__ = ["RuleDiff", "apply_rule_diff", "parse_nl_rule", "supported_grammar"]
