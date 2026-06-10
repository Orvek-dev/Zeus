from __future__ import annotations

from datetime import datetime, timezone
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


class GrantTier(str, Enum):
    """Per-capability autonomy tier inside an envelope.

    ``auto`` executes silently, ``ask_first`` asks once and can be licensed
    into a session grant, ``always_ask`` can never be pre-licensed (hard risk).
    """

    auto = "auto"
    ask_first = "ask_first"
    always_ask = "always_ask"


class CapabilityRequest(BaseModel):
    """Step-2 output: one capability the objective seems to need, with the
    provenance clause that produced it. Untraceable requests never become
    grants — that is what makes "하는 김에" structurally impossible."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    derived_from: str
    args_shape: dict[str, str] = Field(default_factory=dict)

    @field_validator("capability_id", "derived_from")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class GrantedCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    tier: GrantTier
    provenance: str
    path_scopes: tuple[str, ...] = ()
    network_hosts: tuple[str, ...] = ()
    credential_scopes: tuple[str, ...] = ()
    taint_escalates: bool = False
    burned: bool = False

    @field_validator("capability_id", "provenance")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class LockedCapability(BaseModel):
    """An EXPLICIT denial: adjacent-dangerous, not derived from the objective."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    reason: str

    @field_validator("capability_id", "reason")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class VoiQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    unknown_id: str
    question: str
    voi_score: float


class AuthorityEnvelope(BaseModel):
    """The compiled least-authority contract for one objective.

    This is what the Decision API resolves at step 1: granted capabilities
    with tiers and scopes, an explicit lock list, and a budget. One envelope
    per objective; subagents get attenuated child leases derived from it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    envelope_id: str
    objective_id: str
    principal_id: str
    granted: tuple[GrantedCapability, ...] = ()
    lock_list: tuple[LockedCapability, ...] = ()
    questions: tuple[VoiQuestion, ...] = ()
    budget_total_units: int = Field(default=0, ge=0)
    budget_per_run_units: int = Field(default=0, ge=0)
    expires_at: Optional[datetime] = None

    @field_validator("envelope_id", "objective_id", "principal_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    def grant_for(self, capability_id: str) -> Optional[GrantedCapability]:
        for grant in self.granted:
            if grant.capability_id == capability_id and not grant.burned:
                return grant
        return None

    def locked(self, capability_id: str) -> Optional[LockedCapability]:
        for lock in self.lock_list:
            if lock.capability_id == capability_id:
                return lock
        return None

    def approved_hosts(self) -> frozenset[str]:
        hosts: set[str] = set()
        for grant in self.granted:
            hosts.update(grant.network_hosts)
        return frozenset(hosts)

    def expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        timestamp = now if now is not None else datetime.now(timezone.utc)
        return self.expires_at <= timestamp


class EnvelopeStore:
    """Active envelopes by objective. In-memory for the alpha; the store
    interface is what persists, not the dict."""

    def __init__(self) -> None:
        self._by_objective: dict[str, AuthorityEnvelope] = {}

    def put(self, envelope: AuthorityEnvelope) -> None:
        self._by_objective[envelope.objective_id] = envelope

    def active_for(
        self,
        objective_id: Optional[str],
        *,
        now: Optional[datetime] = None,
    ) -> Optional[AuthorityEnvelope]:
        if objective_id is None:
            return None
        envelope = self._by_objective.get(objective_id)
        if envelope is None or envelope.expired(now):
            return None
        return envelope

    def burn(self, objective_id: str, capability_id: str) -> Optional[AuthorityEnvelope]:
        """Mark a grant burned after use (single-use authority)."""
        envelope = self._by_objective.get(objective_id)
        if envelope is None:
            return None
        granted = tuple(
            grant.model_copy(update={"burned": True})
            if grant.capability_id == capability_id
            else grant
            for grant in envelope.granted
        )
        updated = envelope.model_copy(update={"granted": granted})
        self._by_objective[objective_id] = updated
        return updated
