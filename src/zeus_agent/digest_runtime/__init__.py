"""Weekly digest (P6) — where NOTIFY-tier governance sinks instead of pinging.

One readable summary per week: spend by objective/model, decision mix, asks,
new licenses, notify-tier actions. Acking the digest is the dead-man signal
loop governance (P7) watches — an unacked digest demotes autonomy.
"""

from __future__ import annotations

from .digest import (
    KV_DIGEST_LAST_ACK,
    KV_DIGEST_LAST_BUILT,
    ack_digest,
    build_digest,
    license_progress,
)

__all__ = [
    "KV_DIGEST_LAST_ACK",
    "KV_DIGEST_LAST_BUILT",
    "ack_digest",
    "build_digest",
    "license_progress",
]
