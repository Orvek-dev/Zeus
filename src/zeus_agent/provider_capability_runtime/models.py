from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class ProviderVendor(str, Enum):
    """The one provider taxonomy. Every provider call — fake, local, or external —
    flows through a single capability handler keyed by this enum, instead of the
    3+ parallel provider runtimes that existed before."""

    fake = "fake"
    local = "local"
    openai = "openai"
    anthropic = "anthropic"


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    vendor: ProviderVendor
    model_id: str
    message: str
    endpoint: Optional[str] = None
    secret_ref: Optional[str] = None          # env://VAR only; raw keys are rejected
    allowed_models: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ()
    budget_max_units: int = Field(default=32, ge=0)
    budget_requested_units: int = Field(default=1, ge=0)
    timeout_ms: int = Field(default=30000, ge=1)

    @field_validator("model_id", "message")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("endpoint", "secret_ref")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)


class ProviderReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: str
    vendor: ProviderVendor
    model_id: str
    handler_executed: bool = False
    content: Optional[str] = None
    blocked_reason: Optional[str] = None       # pre-execution governance block (no side effect)
    provider_error: Optional[str] = None       # post-network failure (handler DID run)
    evidence_record_id: Optional[str] = None
    broker_evidence_bound: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")
