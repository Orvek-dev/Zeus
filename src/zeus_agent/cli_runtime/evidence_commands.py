from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from .approval_commands import _approval_effect
from .context import echo_json, parse_ts, state_for_home

if TYPE_CHECKING:
    from zeus_agent.trust_loop_runtime import ParkedAction


def register_evidence_commands(app: typer.Typer) -> None:
    @app.command("ledger", help="Inspect the evidence ledger.")
    def ledger(
        tail: int = typer.Option(20, "--tail", help="Show the last N records."),
        why: str | None = typer.Option(None, "--why", help="Walk the causal chain of a record id."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import FlightRecorder, SQLiteEvidenceLedger

        state = state_for_home(home)
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        if why is not None:
            echo_json(list(recorder.why(why)))
            return
        records = recorder.ledger.records()
        echo_json(records[-max(tail, 0):])

    @app.command("why", help="Show why a parked action or record happened.")
    def why(
        parked: str | None = typer.Option(None, "--parked", help="Parked action id."),
        record: str | None = typer.Option(None, "--record", help="Ledger record id."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            SQLiteApprovalQueue,
            SQLiteControlPlaneStore,
            SQLiteEvidenceLedger,
        )

        state = state_for_home(home)
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        if record is not None:
            echo_json({"record_id": record, "chain": list(recorder.why(record))})
            return
        if parked is None:
            raise typer.BadParameter("provide --parked <id> or --record <id>")
        queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
        try:
            item = queue.get(parked)
        except KeyError:
            raise typer.BadParameter("unknown parked_action_id: {0}".format(parked))
        echo_json(
            {
                "parked_action_id": item.parked_action_id,
                "status": item.status,
                "capability_id": item.action.capability_id,
                "host": item.host,
                "session_id": item.session_id,
                "approval_effect": _approval_effect(item),
                "operator_note": (
                    "resolve in Zeus control tower or a separate operator terminal; "
                    "do not paste Zeus commands into the governed host"
                ),
                "timeline": _timeline_for_parked(item, recorder.ledger.records()),
            }
        )

    @app.command("status", help="Control-plane status: coverage, decisions, asks, chain, wallet.")
    def status(home: Path | None = typer.Option(None, "--home")) -> None:
        from zeus_agent.proxy_runtime import (
            KV_LAST_REQUEST_AT,
            KV_LAST_RESPONSE_AT,
            KV_SECRET_FINDINGS,
        )
        from zeus_agent.status_runtime import (
            approval_queue_status_counts,
            grant_status_counts,
            operator_inbox_summary,
            replay_authorization_status_counts,
        )
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            SQLiteControlPlaneStore,
            SQLiteEvidenceLedger,
        )
        from zeus_agent.wallet_runtime import weekly_spend_digest

        state = state_for_home(home)
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        decision_mix: dict[str, int] = {}
        for item in recorder.ledger.records():
            if str(item["kind"]) != "decision_receipt":
                continue
            try:
                payload = json.loads(str(item["payload_json"]))
            except ValueError:
                continue
            decision = str(payload.get("decision", "unknown"))
            decision_mix[decision] = decision_mix.get(decision, 0) + 1
        coverage = recorder.coverage()
        now = datetime.now(timezone.utc)
        store = SQLiteControlPlaneStore(state.state_path)
        watchdog: dict[str, object] = {
            "last_request_at": store.kv_get(KV_LAST_REQUEST_AT),
            "last_response_at": store.kv_get(KV_LAST_RESPONSE_AT),
            "secret_findings": int(store.kv_get(KV_SECRET_FINDINGS) or 0),
        }
        request_at = parse_ts(watchdog["last_request_at"])
        response_at = parse_ts(watchdog["last_response_at"])
        if request_at is not None and (response_at is None or response_at < request_at):
            watchdog["waiting_on_provider_seconds"] = int((now - request_at).total_seconds())
        grants = grant_status_counts(state.load_grants().all(), now_epoch=int(now.timestamp()))
        replay_grants = replay_authorization_status_counts(store, now=now)
        queue_counts = approval_queue_status_counts(store, now=now)
        echo_json(
            {
                "home": str(state.root),
                "coverage": coverage.model_dump(mode="json"),
                "decision_mix": decision_mix,
                "asks": decision_mix.get("ask", 0),
                "chain_ok": recorder.ledger.verify_chain().ok,
                "standing_grants": grants["active"],
                "grants": grants,
                "grant_inventory": {
                    "standing": grants,
                    "replay_authorizations": replay_grants,
                },
                "approval_queue": queue_counts,
                "operator_inbox": operator_inbox_summary(queue_counts),
                "wallet_week": weekly_spend_digest(recorder, now=now),
                "budgets": [
                    {"scope": row[0], "id": row[1], "limit_units": row[2], "spent_units": row[3]}
                    for row in store.budget_rows()
                ],
                "proxy": watchdog,
            }
        )


def _timeline_for_parked(
    parked: ParkedAction, records: list[dict[str, object]]
) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    decision_receipt_ids = _decision_receipt_ids_for_parked(parked, records)
    for record in records:
        payload = _record_payload(record)
        if not _matches_parked(parked, record, payload, decision_receipt_ids):
            continue
        row: dict[str, object] = {
            "seq": record["seq"],
            "record_id": record["record_id"],
            "kind": record["kind"],
            "run_id": record["run_id"],
            "capability_id": payload.get("capability_id"),
        }
        for field in ("host", "surface", "decision", "reason", "governed"):
            if field in payload:
                row[field] = payload[field]
        if "decision_receipt_record_id" in payload:
            row["decision_receipt_record_id"] = payload["decision_receipt_record_id"]
        timeline.append(row)
    return timeline


def _decision_receipt_ids_for_parked(
    parked: ParkedAction, records: list[dict[str, object]]
) -> set[str]:
    receipt_ids: set[str] = set()
    for record in records:
        if str(record["kind"]) != "decision_receipt":
            continue
        payload = _record_payload(record)
        if _decision_receipt_matches_parked(parked, record, payload):
            receipt_ids.add(str(record["record_id"]))
    return receipt_ids


def _decision_receipt_matches_parked(
    parked: ParkedAction, record: dict[str, object], payload: dict[str, object]
) -> bool:
    if str(record["run_id"]) != parked.action.run_id:
        return False
    if payload.get("capability_id") != parked.action.capability_id:
        return False
    if parked.session_id and payload.get("session_id") not in {None, parked.session_id}:
        return False
    action_id = payload.get("action_id")
    if action_id is not None:
        return action_id == parked.action.action_id
    action_payload_hash = payload.get("action_payload_hash")
    if action_payload_hash is not None:
        return action_payload_hash == parked.payload_hash
    return payload.get("args") == parked.action.payload


def _matches_parked(
    parked: ParkedAction,
    record: dict[str, object],
    payload: dict[str, object],
    decision_receipt_ids: set[str],
) -> bool:
    kind = str(record["kind"])
    if kind == "decision_receipt":
        return str(record["record_id"]) in decision_receipt_ids
    if kind == "gate_observation":
        receipt_id = payload.get("decision_receipt_record_id")
        return isinstance(receipt_id, str) and receipt_id in decision_receipt_ids
    return False


def _record_payload(record: dict[str, object]) -> dict[str, object]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}
