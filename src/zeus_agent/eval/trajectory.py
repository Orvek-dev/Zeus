"""Trajectory export and compression."""

from __future__ import annotations

from pathlib import Path

from zeus_agent.agent.context import compact_text
from zeus_agent.core.mneme import list_evidence
from zeus_agent.storage.artifacts import persist_json_artifact
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.run_store import RunStore


def export_run_trajectory(
    run_id: str,
    *,
    home: Path | None = None,
    max_event_payload_chars: int = 1500,
) -> Path:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    events = [
        {
            **event,
            "payload": compact_text(str(event.get("payload", "")), max_chars=max_event_payload_chars),
        }
        for event in EventLog(store.home).read_all()
        if event.get("run_id") in {run_id, None}
    ]
    payload = {
        "schema_version": "zeus.trajectory.v1",
        "run_id": run_id,
        "goal_contract": contract.model_dump(mode="json"),
        "execution_spec": spec.model_dump(mode="json"),
        "evidence": list_evidence(run_id, home=store.home),
        "events": events,
    }
    return persist_json_artifact(run_id, "trajectory", "trajectory.json", payload, home=store.home)

