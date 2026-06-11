from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.decision_api_runtime import DecisionResponse, Obligation
from zeus_agent.digest_runtime import KV_DIGEST_LAST_ACK
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteControlPlaneStore,
    TrustDecision,
)

KV_FORCE_ASK: Final = "governor.force_ask_reason"
_LEASE_PREFIX: Final = "lease."
_DEADMAN_MAX_AGE_DAYS: Final = 10


# ---------------------------------------------------------------- standing lease
class StandingLease(BaseModel):
    """A recurring objective's authority, with a renewal heartbeat. Expiry is
    not an alert — the renewal checkpoint is an ASK before the next run."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    lease_id: str
    objective_id: str
    cadence_days: int = Field(gt=0)
    last_renewed_at: datetime

    def renewal_due(self, *, now: datetime) -> bool:
        return now >= self.last_renewed_at + timedelta(days=self.cadence_days)


def lease_save(store: SQLiteControlPlaneStore, lease: StandingLease) -> None:
    store.kv_set(_LEASE_PREFIX + lease.lease_id, lease.model_dump_json())


def lease_load(store: SQLiteControlPlaneStore, lease_id: str) -> Optional[StandingLease]:
    raw = store.kv_get(_LEASE_PREFIX + lease_id)
    if raw is None:
        return None
    try:
        return StandingLease.model_validate_json(raw)
    except ValueError:
        return None


def lease_renew(
    store: SQLiteControlPlaneStore, lease: StandingLease, *, now: datetime
) -> StandingLease:
    renewed = lease.model_copy(update={"last_renewed_at": now})
    lease_save(store, renewed)
    return renewed


# -------------------------------------------------------------------- dead-man
def check_deadman(
    store: SQLiteControlPlaneStore,
    *,
    now: datetime,
    max_age_days: int = _DEADMAN_MAX_AGE_DAYS,
) -> dict[str, JsonValue]:
    """An unacked digest means nobody is watching: demote autonomy so every
    side-effecting call asks until the human resurfaces. Enforced pre-call via
    the governor bank, not by a notification."""
    raw = store.kv_get(KV_DIGEST_LAST_ACK)
    last_ack: Optional[datetime] = None
    if raw is not None:
        try:
            last_ack = datetime.fromisoformat(raw)
        except ValueError:
            last_ack = None
    stale = last_ack is None or now - last_ack > timedelta(days=max_age_days)
    if stale:
        store.kv_set(KV_FORCE_ASK, "deadman_unacked_digest")
        return {"demoted": True, "reason": "deadman_unacked_digest", "last_ack": raw}
    return {"demoted": False, "last_ack": raw}


def restore_autonomy(store: SQLiteControlPlaneStore) -> None:
    store.kv_set(KV_FORCE_ASK, "")


# ------------------------------------------------------------------ quiet hours
def in_quiet_hours(now: datetime, spec: Optional[str]) -> bool:
    """spec "22-07": inclusive start hour, exclusive end hour, wraps midnight."""
    if not spec or "-" not in spec:
        return False
    try:
        start, end = (int(part) % 24 for part in spec.split("-", 1))
    except ValueError:
        return False
    hour = now.hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def apply_quiet_hours(
    response: DecisionResponse, *, now: datetime, spec: Optional[str]
) -> DecisionResponse:
    """ASK during quiet hours stays parked and carries quiet_hold — surfaces
    route it to the morning digest instead of waking anyone."""
    if response.decision is not TrustDecision.ASK or not in_quiet_hours(now, spec):
        return response
    if Obligation.quiet_hold in response.obligations:
        return response
    return response.model_copy(
        update={"obligations": response.obligations + (Obligation.quiet_hold,)}
    )


# ------------------------------------------------------------------ drift watch
def drift_report(
    recorder: FlightRecorder, *, now: datetime, window_days: int = 7
) -> dict[str, JsonValue]:
    """Action-mix drift: current window's capability distribution vs the
    previous window's (L1 distance, 0=identical .. 2=disjoint). Reported in
    the digest; policy may choose to escalate on it later."""
    current: dict[str, int] = {}
    previous: dict[str, int] = {}
    cutoff = now - timedelta(days=window_days)
    prior_cutoff = now - timedelta(days=2 * window_days)
    for record in recorder.ledger.records():
        if str(record["kind"]) != "decision_receipt":
            continue
        try:
            created = datetime.fromisoformat(str(record["created_at"]))
        except ValueError:
            continue
        payload = _payload_of(record)
        capability_id = str(payload.get("capability_id", "unknown"))
        if created >= cutoff:
            current[capability_id] = current.get(capability_id, 0) + 1
        elif created >= prior_cutoff:
            previous[capability_id] = previous.get(capability_id, 0) + 1
    score = _l1_distance(current, previous)
    return {
        "window_days": window_days,
        "current_actions": sum(current.values()),
        "previous_actions": sum(previous.values()),
        "drift_score": score,
        "novel_capabilities": sorted(set(current) - set(previous)),
    }


def _l1_distance(current: dict[str, int], previous: dict[str, int]) -> float:
    current_total = sum(current.values())
    previous_total = sum(previous.values())
    if current_total == 0 or previous_total == 0:
        return 0.0
    keys = set(current) | set(previous)
    distance = sum(
        abs(current.get(key, 0) / current_total - previous.get(key, 0) / previous_total)
        for key in keys
    )
    return round(distance, 4)


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
