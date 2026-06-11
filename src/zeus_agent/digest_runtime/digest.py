from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.trust_loop_runtime import FlightRecorder, SQLiteControlPlaneStore, SQLiteTrustStatStore
from zeus_agent.wallet_runtime import weekly_spend_digest

KV_DIGEST_LAST_ACK: Final = "digest.last_ack"
KV_DIGEST_LAST_BUILT: Final = "digest.last_built"
# a capability earns its "license" (auto-approval candidacy) at this many
# successful, evidenced runs — surfaced as progress, decided by policy.
LICENSE_RUNS: Final = 30


def build_digest(
    recorder: FlightRecorder,
    store: SQLiteControlPlaneStore,
    trust_stats: Optional[SQLiteTrustStatStore],
    *,
    now: datetime,
    days: int = 7,
) -> dict[str, JsonValue]:
    cutoff = now - timedelta(days=days)
    decision_mix: dict[str, int] = {}
    notify_items: list[dict[str, JsonValue]] = []
    for record in recorder.ledger.records():
        if str(record["kind"]) != "decision_receipt":
            continue
        created = _created_at(record)
        if created is None or created < cutoff:
            continue
        payload = _payload_of(record)
        decision = str(payload.get("decision", "unknown"))
        decision_mix[decision] = decision_mix.get(decision, 0) + 1
        if decision == "notify":
            notify_items.append(
                {
                    "capability_id": payload.get("capability_id"),
                    "reason": payload.get("reason"),
                    "record_id": record["record_id"],
                }
            )
    digest: dict[str, JsonValue] = {
        "window_days": days,
        "spend": weekly_spend_digest(recorder, now=now, days=days),
        "decision_mix": decision_mix,
        "asks": decision_mix.get("ask", 0),
        "notify_items": notify_items[:50],
        "licenses": license_progress(trust_stats),
        "active_pack": store.kv_get("policy.active_pack"),
        "built_at": now.isoformat(),
    }
    store.kv_set(KV_DIGEST_LAST_BUILT, now.isoformat())
    recorder.record_decision(
        run_id="run.digest",
        payload={
            "capability_id": "digest.generate",
            "decision": "notify",
            "reason": "weekly_digest",
            "asks": digest["asks"],
        },
    )
    return digest


def ack_digest(store: SQLiteControlPlaneStore, *, now: datetime) -> dict[str, JsonValue]:
    """The human read it — the dead-man switch resets from this timestamp."""
    store.kv_set(KV_DIGEST_LAST_ACK, now.isoformat())
    return {"acked_at": now.isoformat()}


def license_progress(trust_stats: Optional[SQLiteTrustStatStore]) -> list[dict[str, JsonValue]]:
    if trust_stats is None:
        return []
    rows: list[dict[str, JsonValue]] = []
    for capability_id, (success, failure) in sorted(trust_stats.all().items()):
        rows.append(
            {
                "capability_id": capability_id,
                "successes": success,
                "failures": failure,
                "license": "{0}/{1}".format(min(success, LICENSE_RUNS), LICENSE_RUNS),
                "licensed": success >= LICENSE_RUNS and failure == 0,
            }
        )
    return rows


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _created_at(record: dict[str, JsonValue]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(record["created_at"]))
    except ValueError:
        return None
