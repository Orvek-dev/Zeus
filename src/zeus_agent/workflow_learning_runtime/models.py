from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

WorkflowCritiqueMemoryDecision = Literal["recorded", "blocked"]


class WorkflowCritiqueMemoryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: WorkflowCritiqueMemoryDecision
    selected_checkpoint: Optional[dict[str, JsonValue]] = None
    selected_fact: Optional[dict[str, JsonValue]] = None
    fact_count: int
    quarantined_count: int
    blocked_reasons: tuple[str, ...] = ()
    memory_store_local: bool = True
    retention_policy: str = "local_review_required"
    memory_promoted: bool = False
    wiki_page_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
