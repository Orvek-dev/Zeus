from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, JsonValue


class GovernedObjectiveResult(BaseModel):
    """The unified result of the assembled spine: card + (if started) run state.

    One object answers "what did Zeus understand, what plan did it verify, did it
    run, where did it stop, and what evidence backs it" — the end-to-end view that
    was missing while the components were islands.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    stage: str  # compiled | waiting_approval | completed | failed | blocked
    run_id: Optional[str] = None
    card: dict[str, JsonValue]
    run: Optional[dict[str, JsonValue]] = None
    questions: tuple[str, ...] = ()
    capability_gaps: tuple[str, ...] = ()
    evidence_record_count: int = 0

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
