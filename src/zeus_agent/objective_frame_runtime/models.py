from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from zeus_agent.objective_card_runtime import ObjectiveFrameInput


class FrameParseResult(BaseModel):
    """Outcome of turning a raw LLM output into a validated objective frame.

    Fail-closed: a malformed or secret-bearing output yields ``decision='blocked'``
    with no frame and no echoed secret span.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: str
    frame: Optional[ObjectiveFrameInput] = None
    blocked_reason: Optional[str] = None
    no_secret_echo: bool = True

    @property
    def ok(self) -> bool:
        return self.decision == "frame" and self.frame is not None
