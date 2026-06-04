from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int

    def allows(self, attempts: int) -> bool:
        return attempts <= self.max_attempts


class LiveAgentLoopResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["selected", "blocked"]
    blocked_reasons: tuple[str, ...] = ()
    provider_decision: Literal["selected", "blocked"]
    provider_turns: int = Field(ge=0)
    streaming_chunks_recorded: bool
    tool_calls_processed: int = Field(ge=0)
    tool_result_recorded: bool
    evidence_records: int = Field(ge=0)
    audit_events: int = Field(ge=0)
    audit_record_created: bool
    session_persisted: bool
    verification_completion_allowed: bool
    handler_executed: bool
    network_opened: bool
    no_secret_echo: bool
    live_production_claimed: bool = False
