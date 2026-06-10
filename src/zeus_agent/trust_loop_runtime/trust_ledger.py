from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from .models import ActionRisk, Reversibility, TrustLoopAction, require_text
from .trust_stat_store import SQLiteTrustStatStore


class TrustStat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)

    @field_validator("capability_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value, "capability_id")


class GrantProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    proposal_id: str
    capability_id: str
    reason: str
    requires_human_review: bool = True
    auto_applied: bool = False

    @field_validator("proposal_id", "capability_id", "reason")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class TrustLedger:
    """Earned-trust counts per capability.

    Defaults to in-memory (back-compat). Pass a ``SQLiteTrustStatStore`` to make
    trust durable across restarts — the fix for the earned-autonomy leak. Reads
    and writes route through the store when present, the dict otherwise.
    """

    def __init__(self, *, store: Optional[SQLiteTrustStatStore] = None) -> None:
        self._store = store
        self._stats: dict[str, TrustStat] = {}

    def record_success(self, action: TrustLoopAction) -> TrustStat:
        current = self._get(action.capability_id)
        updated = current.model_copy(update={"success_count": current.success_count + 1})
        self._put(updated)
        return updated

    def record_failure(self, action: TrustLoopAction) -> TrustStat:
        current = self._get(action.capability_id)
        updated = current.model_copy(update={"failure_count": current.failure_count + 1})
        self._put(updated)
        return updated

    def stat(self, capability_id: str) -> TrustStat:
        return self._get(capability_id)

    def _get(self, capability_id: str) -> TrustStat:
        if self._store is not None:
            row = self._store.get(capability_id)
            if row is None:
                return _empty_stat(capability_id)
            return TrustStat(capability_id=capability_id, success_count=row[0], failure_count=row[1])
        return self._stats.get(capability_id, _empty_stat(capability_id))

    def _put(self, stat: TrustStat) -> None:
        if self._store is not None:
            self._store.upsert(
                stat.capability_id,
                success_count=stat.success_count,
                failure_count=stat.failure_count,
            )
        else:
            self._stats[stat.capability_id] = stat

    def propose_grant(self, action: TrustLoopAction) -> GrantProposal | None:
        stat = self._get(action.capability_id)
        if stat.success_count < 3 or stat.failure_count > 0:
            return None
        if action.risk is not ActionRisk.low or action.reversibility is not Reversibility.reversible:
            return None
        return GrantProposal(
            proposal_id="trust.grant_proposal.{0}".format(action.capability_id.replace(".", "_")),
            capability_id=action.capability_id,
            reason="repeated_low_risk_reversible_success",
        )


def _empty_stat(capability_id: str) -> TrustStat:
    return TrustStat(capability_id=capability_id, success_count=0, failure_count=0)
