from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility


class CommandRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    program: str
    side_effect: SideEffectClass
    reversibility: Reversibility
    risk: ActionRisk
    reasons: tuple[str, ...]


def make_risk(
    program: str,
    side_effect: SideEffectClass,
    reversibility: Reversibility,
    risk: ActionRisk,
    reasons: tuple[str, ...],
) -> CommandRisk:
    return CommandRisk(
        program=program,
        side_effect=side_effect,
        reversibility=reversibility,
        risk=risk,
        reasons=reasons,
    )
