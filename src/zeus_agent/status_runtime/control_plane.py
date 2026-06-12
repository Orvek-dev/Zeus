from __future__ import annotations

from datetime import datetime

from zeus_agent.graded_approval_runtime import ApprovalGrant
from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

_GRANT_ZERO = {"active": 0, "consumed": 0, "expired": 0, "total": 0}
_QUEUE_ZERO = {
    "pending": 0,
    "approved": 0,
    "rejected": 0,
    "expired": 0,
    "superseded": 0,
    "total": 0,
}


def grant_status_counts(grants: tuple[ApprovalGrant, ...], *, now_epoch: int) -> dict[str, int]:
    counts = dict(_GRANT_ZERO)
    counts["total"] = len(grants)
    for grant in grants:
        if grant.consumed:
            counts["consumed"] += 1
        elif grant.expires_at_epoch != 0 and now_epoch >= grant.expires_at_epoch:
            counts["expired"] += 1
        else:
            counts["active"] += 1
    return counts


def replay_authorization_status_counts(
    store: SQLiteControlPlaneStore, *, now: datetime
) -> dict[str, int]:
    counts = dict(_GRANT_ZERO)
    rows = store.replay_rows()
    counts["total"] = len(rows)
    for row in rows:
        expires_at = datetime.fromisoformat(row[6])
        consumed_at = row[7]
        if consumed_at:
            counts["consumed"] += 1
        elif now >= expires_at:
            counts["expired"] += 1
        else:
            counts["active"] += 1
    return counts


def approval_queue_status_counts(
    store: SQLiteControlPlaneStore, *, now: datetime
) -> dict[str, int]:
    store.queue_expire_due(now.isoformat())
    counts = dict(_QUEUE_ZERO)
    rows = store.queue_rows()
    counts["total"] = len(rows)
    for row in rows:
        status = row[3]
        if status in counts:
            counts[status] += 1
    return counts


def operator_inbox_summary(queue_counts: dict[str, int]) -> dict[str, int]:
    return {
        "pending_asks": queue_counts["pending"],
        "resolved_history": (
            queue_counts["approved"]
            + queue_counts["rejected"]
            + queue_counts["expired"]
            + queue_counts["superseded"]
        ),
    }
