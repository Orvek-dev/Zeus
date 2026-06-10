from __future__ import annotations

from zeus_agent.goal_intelligence_runtime.intent import IntentFrame


def intent_seed(frame: IntentFrame) -> str:
    """Turn the goal-intelligence safety pre-pass into a SEED hint for the LLM —
    not a 1:1 frame. The IntentFrame's unknowns are meta-gaps ("acceptance_criteria"),
    so we pass them as context the cognitive layer can resolve, never as the
    domain unknowns the risk engine consumes.
    """
    parts: list[str] = ["desired_outcome: {0}".format(frame.desired_outcome)]
    if frame.acceptance_criteria:
        parts.append("acceptance_criteria_hint: " + "; ".join(frame.acceptance_criteria))
    if frame.constraints:
        parts.append("constraints_hint: " + "; ".join(frame.constraints))
    if frame.entities:
        parts.append("entities_hint: " + "; ".join(frame.entities))
    if frame.unknowns:
        parts.append("open_meta_gaps: " + "; ".join(frame.unknowns))
    parts.append("confidence_hint: {0:.2f}".format(frame.confidence))
    return " | ".join(parts)
