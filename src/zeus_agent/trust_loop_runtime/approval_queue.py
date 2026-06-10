from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from .models import TrustLoopAction, require_text

ParkedActionStatus = Literal["pending", "approved", "rejected", "expired", "superseded"]


class ParkedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    parked_action_id: str
    action: TrustLoopAction
    status: ParkedActionStatus = "pending"
    created_at: datetime
    expires_at: datetime

    @field_validator("parked_action_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value, "parked_action_id")


class ApprovalQueue:
    def __init__(self) -> None:
        self._actions: dict[str, ParkedAction] = {}
        self._active_by_action_id: dict[str, str] = {}

    def park(self, action: TrustLoopAction, *, ttl_seconds: int = 600) -> ParkedAction:
        created_at = datetime.now(timezone.utc)
        active_id = self._active_by_action_id.get(action.action_id)
        if active_id is not None:
            current = self._actions[active_id]
            self._actions[active_id] = current.model_copy(update={"status": "superseded"})
        parked = ParkedAction(
            parked_action_id=_parked_action_id(action, len(self._actions) + 1),
            action=action,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
        )
        self._actions[parked.parked_action_id] = parked
        self._active_by_action_id[action.action_id] = parked.parked_action_id
        return parked

    def get(self, parked_action_id: str) -> ParkedAction:
        return self._actions[parked_action_id]

    def pending(self, *, now: datetime) -> tuple[ParkedAction, ...]:
        refreshed = []
        for parked in self._actions.values():
            refreshed.append(_expire_if_needed(parked, now=now))
        self._actions = {parked.parked_action_id: parked for parked in refreshed}
        return tuple(parked for parked in refreshed if parked.status == "pending")


def _expire_if_needed(parked: ParkedAction, *, now: datetime) -> ParkedAction:
    if parked.status != "pending":
        return parked
    if parked.expires_at <= now:
        return parked.model_copy(update={"status": "expired"})
    return parked


def _parked_action_id(action: TrustLoopAction, seq: int) -> str:
    return "trust.parked.{0}.{1}".format(action.action_id.replace(".", "_"), seq)
