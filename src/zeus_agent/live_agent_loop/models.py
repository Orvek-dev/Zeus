from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.agent_runtime.live_loop_models import LiveAgentLoopResult, RetryPolicy
from zeus_agent.security.credentials import redact_secret_spans


class LiveAgentLoopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    request_id: str
    objective_id: str
    message: str
    evidence_target: str
    provider_kind: Literal["fake", "local_llm"] = "fake"

    @field_validator("request_id", "objective_id", "evidence_target")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("identifier must be non-empty")
        return redact_secret_spans(normalized)

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("message must be non-empty")
        return redact_secret_spans(normalized)


__all__ = ["LiveAgentLoopRequest", "LiveAgentLoopResult", "RetryPolicy"]
