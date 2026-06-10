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

from zeus_agent.trust_loop_runtime import Reversibility


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class VerbClass(str, Enum):
    fetch = "fetch"
    transform = "transform"
    generate = "generate"
    publish = "publish"
    notify = "notify"
    store = "store"
    approve = "approve"
    observe = "observe"


class SideEffectClass(str, Enum):
    """Escalating blast radius of a capability's effect.

    This field, not an LLM's opinion, is where the workflow safety checks
    (approval dominance, taint flow) anchor. It is set by code review for
    builtins and by conservative default for imported MCP tools.
    """

    none = "none"
    local_write = "local_write"
    account_write = "account_write"
    public_write = "public_write"


class CostConfidence(str, Enum):
    measured = "measured"
    estimated = "estimated"
    unknown = "unknown"


class Provenance(str, Enum):
    builtin = "builtin"
    mcp = "mcp"
    learned = "learned"


class CapabilityStatus(str, Enum):
    active = "active"
    quarantined = "quarantined"
    deprecated = "deprecated"


class CostModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    fixed_per_call_units: float = Field(default=0.0, ge=0.0)
    per_1k_tokens_in_units: float = Field(default=0.0, ge=0.0)
    per_1k_tokens_out_units: float = Field(default=0.0, ge=0.0)
    confidence: CostConfidence = CostConfidence.unknown


class CapabilityTrust(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    score: float = Field(ge=0.0, le=1.0)
    runs: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    measured: bool = False


class CapabilityRecord(BaseModel):
    """Registry overlay for one capability.

    Keyed by ``capability_id`` matching a kernel ``CapabilityDescriptor``. The
    kernel stays minimal; this record carries the cost/trust/effect metadata the
    workflow synthesiser and budget rollup need.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    verb_class: VerbClass
    title: str
    input_summary: str
    output_summary: str
    side_effect: SideEffectClass
    reversibility: Reversibility
    compensation_ref: Optional[str] = None
    cost_model: CostModel = Field(default_factory=CostModel)
    trust: CapabilityTrust
    provenance: Provenance
    status: CapabilityStatus
    schema_hash: Optional[str] = None
    server_ref: Optional[str] = None

    @field_validator("capability_id", "title", "input_summary", "output_summary")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("compensation_ref", "schema_hash", "server_ref")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)

    @property
    def usable_without_approval(self) -> bool:
        """Active, no-side-effect capabilities are the only ones a plan may
        bind without an explicit approval gate preceding them."""
        return self.status is CapabilityStatus.active and self.side_effect is SideEffectClass.none


class CatalogEntry(BaseModel):
    """Projection handed to the LLM during synthesis.

    Deliberately excludes credential refs and authority scopes — the synthesiser
    needs to know WHAT is possible, not WITH WHICH secret. Authority binding is
    the deterministic verification layer's job.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    verb_class: VerbClass
    title: str
    io_summary: str
    cost_summary: str
    side_effect: SideEffectClass
    trust_score: float
    status: CapabilityStatus
