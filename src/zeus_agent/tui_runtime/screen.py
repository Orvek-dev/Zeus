from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import JsonValue
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zeus_agent.operator_inbox_runtime import approval_effect_for, pending_card
from zeus_agent.status_runtime import (
    approval_queue_status_counts,
    grant_status_counts,
    operator_inbox_summary,
    replay_authorization_status_counts,
)
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)


@dataclass(frozen=True, slots=True)
class TuiSnapshot:
    home: str
    chain_ok: bool
    decision_mix: dict[str, int]
    pending_cards: tuple[dict[str, JsonValue], ...]
    active_grants: int
    active_replay_tokens: int
    pending_asks: int
    resolved_history: int


def build_snapshot(state) -> TuiSnapshot:
    store = SQLiteControlPlaneStore(state.state_path)
    recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
    now = datetime.now(timezone.utc)
    queue = SQLiteApprovalQueue(store)
    pending = []
    for parked in queue.pending(now=now):
        card = pending_card(parked)
        card["run_id"] = parked.action.run_id
        card["approval_effect"] = approval_effect_for(parked)
        pending.append(card)
    grants = grant_status_counts(state.load_grants().all(), now_epoch=int(now.timestamp()))
    replay = replay_authorization_status_counts(store, now=now)
    queue_counts = approval_queue_status_counts(store, now=now)
    inbox = operator_inbox_summary(queue_counts)
    return TuiSnapshot(
        home=str(state.root),
        chain_ok=recorder.ledger.verify_chain().ok,
        decision_mix=_decision_mix(recorder),
        pending_cards=tuple(pending),
        active_grants=grants["active"],
        active_replay_tokens=replay["active"],
        pending_asks=inbox["pending_asks"],
        resolved_history=inbox["resolved_history"],
    )


def render_snapshot(snapshot: TuiSnapshot, console: Console) -> None:
    status = Table.grid(expand=True)
    status.add_column()
    status.add_column(justify="right")
    status.add_row(
        "ASK {0}  AUTO {1}  NOTIFY {2}  DENY {3}  GRANTS {4}  REPLAY {5}".format(
            snapshot.decision_mix.get("ask", 0),
            snapshot.decision_mix.get("auto", 0),
            snapshot.decision_mix.get("notify", 0),
            snapshot.decision_mix.get("deny", 0),
            snapshot.active_grants,
            snapshot.active_replay_tokens,
        ),
        "chain {0}  pending asks {1}".format("ok" if snapshot.chain_ok else "broken", snapshot.pending_asks),
    )
    console.print(Panel(status, title="ZEUS CONTROL TOWER", subtitle=snapshot.home))
    table = Table(title="Pending Approval Inbox", expand=True)
    for column in ("short", "host", "capability", "risk", "effect", "parked id"):
        table.add_column(column)
    for card in snapshot.pending_cards:
        table.add_row(
            str(card.get("short_id", "")),
            str(card.get("host", "")),
            str(card.get("capability_id", "")),
            str(card.get("risk", "")),
            str(card.get("approval_effect", "")),
            str(card.get("parked_action_id", ""))[-18:],
        )
    if not snapshot.pending_cards:
        table.add_row("-", "-", "no pending approvals", "-", "-", "-")
    console.print(table)
    console.print("actions: [o] approve once  [a] remember scoped  [d] deny  [r] refresh  [q] quit")


def _decision_mix(recorder: FlightRecorder) -> dict[str, int]:
    mix: dict[str, int] = {}
    for item in recorder.ledger.records():
        if str(item["kind"]) != "decision_receipt":
            continue
        try:
            payload = json.loads(str(item["payload_json"]))
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        decision = str(payload.get("decision", "unknown"))
        mix[decision] = mix.get(decision, 0) + 1
    return mix
