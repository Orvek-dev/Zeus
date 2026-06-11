"""Consequence engine (P6): vetted plain-language answers, or escalation.

(capability family × side effect × reversibility) → a Korean plain-mode
template answering the five questions. The rule that makes this governance
rather than copywriting: NO TEMPLATE → AUTO-ESCALATE — what Zeus cannot
explain in plain language, Zeus does not run silently. That rule is ENFORCED
inside ``ZeusDecisionEngine.decide()`` (via the injected ``explainability``
check), so the receipt itself becomes ASK — not a post-hoc gate mutation.
``explain()`` is the single source of truth for "is there a vetted card?".
"""

from __future__ import annotations

from .engine import (
    ConsequenceCard,
    explain,
    render_plain_card,
)

__all__ = ["ConsequenceCard", "explain", "render_plain_card"]
