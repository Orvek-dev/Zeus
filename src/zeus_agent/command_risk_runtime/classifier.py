from __future__ import annotations

import re
from typing import Final

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility

from .models import CommandRisk, make_risk
from .segments import classify_segment

_SEPARATOR_RE: Final = re.compile(r"&&|\|\||;|\|")
_RISK_RANK: Final[dict[ActionRisk, int]] = {
    ActionRisk.low: 0,
    ActionRisk.medium: 1,
    ActionRisk.high: 2,
}


def classify_command(command: str) -> CommandRisk:
    text = command.strip()
    if text == "":
        return make_risk("", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("empty_command",))
    if "| sh" in text or "| bash" in text or "|sh" in text or "|bash" in text:
        return make_risk(
            "?",
            SideEffectClass.account_write,
            Reversibility.irreversible,
            ActionRisk.high,
            ("pipe_to_shell",),
        )
    segments = [segment.strip() for segment in _SEPARATOR_RE.split(text) if segment.strip()]
    if len(segments) > 1:
        worst = max((classify_segment(segment) for segment in segments), key=_severity)
        return worst.model_copy(update={"reasons": ("compound_command", *worst.reasons)})
    return classify_segment(text)


def _severity(risk: CommandRisk) -> tuple[int, bool]:
    return (_RISK_RANK[risk.risk], risk.reversibility is Reversibility.irreversible)
