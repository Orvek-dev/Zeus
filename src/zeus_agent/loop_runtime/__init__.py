"""Loop governance (P7): the open niche — long-running and parallel agents.

Notification is not governance: everything here stops or escalates the NEXT
call, before it spends. Standing leases expire into renewal checkpoints; an
unacked weekly digest trips the dead-man switch and demotes autonomy; quiet
hours hold asks for the morning; novelty and fleet ceilings live in the
governor bank itself.
"""

from __future__ import annotations

from .loop import (
    KV_FORCE_ASK,
    StandingLease,
    apply_quiet_hours,
    check_deadman,
    drift_report,
    in_quiet_hours,
    lease_load,
    lease_renew,
    lease_save,
    restore_autonomy,
)

__all__ = [
    "KV_FORCE_ASK",
    "StandingLease",
    "apply_quiet_hours",
    "check_deadman",
    "drift_report",
    "in_quiet_hours",
    "lease_load",
    "lease_renew",
    "lease_save",
    "restore_autonomy",
]
