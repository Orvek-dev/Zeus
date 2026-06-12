from __future__ import annotations

import json

from zeus_agent.governed_objective_runtime import GovernedObjectiveOrchestrator
from zeus_agent.objective_card_runtime import ObjectiveFrameInput

# A ready-to-start objective: a gated publish DAG with full coverage and no
# unanswered questions or gaps. This exercises the WHOLE spine end to end.
_READY_FRAME = {
    "normalized_objective": "Publish a governed summary",
    "triage": "oneshot",
    "required_criteria": ["written"],
    "candidates": [
        {
            "candidate_id": "pub",
            "nodes": [
                {"node_id": "draft", "kind": "llm_generic", "produces_criteria": ["written"]},
                {"node_id": "critic", "kind": "verification", "verifies_criteria": ["written"]},
                {"node_id": "approve", "kind": "approval_gate"},
                {"node_id": "publish", "kind": "capability", "capability_ref": "mcp.blog.publish",
                 "side_effect": "public_write"},
            ],
            "edges": [
                {"src": "draft", "dst": "critic"},
                {"src": "critic", "dst": "approve"},
                {"src": "approve", "dst": "publish"},
            ],
        }
    ],
}


def _frame(data: dict) -> ObjectiveFrameInput:
    return ObjectiveFrameInput.model_validate(data)


def test_full_spine_compiles_runs_suspends_resumes_completes(tmp_path) -> None:
    orch = GovernedObjectiveOrchestrator(home=tmp_path)

    # 1) frame → card → executor: a side-effecting publish suspends at its gate.
    started = orch.compile_and_run(_frame(_READY_FRAME))
    assert started.stage == "waiting_approval"
    assert started.run_id is not None
    assert started.run["node_states"]["publish"] == "pending"

    # 2) resume past the approved gate → publish executes → completed by evidence.
    resumed = orch.resume(started.run_id, approved_gates=("approve",))
    assert resumed.stage == "completed"
    assert resumed.run["node_states"]["publish"] == "succeeded"
    assert resumed.evidence_record_count > 0


def test_not_ready_objective_does_not_execute(tmp_path) -> None:
    # An objective with an unanswered hard-rule question never starts.
    frame = {
        "normalized_objective": "Automate publishing somewhere",
        "triage": "automation",
        "unknowns": [{"unknown_id": "target", "description": "Where to publish?", "risk_class": "external"}],
        "candidates": _READY_FRAME["candidates"],
        "required_criteria": ["written"],
    }
    result = GovernedObjectiveOrchestrator(home=tmp_path).compile_and_run(_frame(frame))
    assert result.stage == "compiled"
    assert result.run is None
    assert result.questions  # the card surfaced a question instead of running


def test_gap_objective_blocks_before_execution(tmp_path) -> None:
    frame = {
        "normalized_objective": "Post to an unconnected service",
        "triage": "oneshot",
        "candidates": [
            {
                "candidate_id": "withgap",
                "nodes": [
                    {"node_id": "draft", "kind": "llm_generic"},
                    {"node_id": "pub", "kind": "gap", "missing_capability": "mcp.tistory.publish"},
                ],
                "edges": [{"src": "draft", "dst": "pub"}],
            }
        ],
    }
    result = GovernedObjectiveOrchestrator(home=tmp_path).compile_and_run(_frame(frame))
    assert result.stage == "compiled"  # card decision needs_connections, not started
    assert result.capability_gaps == ("mcp.tistory.publish",)
    assert result.run is None


def test_resume_without_approval_stays_suspended(tmp_path) -> None:
    orch = GovernedObjectiveOrchestrator(home=tmp_path)
    started = orch.compile_and_run(_frame(_READY_FRAME))
    still = orch.resume(started.run_id, approved_gates=())
    assert still.stage == "waiting_approval"
    assert still.run["node_states"]["publish"] == "pending"


def test_result_payload_is_json_serializable(tmp_path) -> None:
    orch = GovernedObjectiveOrchestrator(home=tmp_path)
    result = orch.compile_and_run(_frame(_READY_FRAME))
    # The whole governed result round-trips to JSON (CLI/library surface).
    json.dumps(result.to_payload())


def test_evidence_timeline_traces_the_run(tmp_path) -> None:
    orch = GovernedObjectiveOrchestrator(home=tmp_path)
    started = orch.compile_and_run(_frame(_READY_FRAME))
    orch.resume(started.run_id, approved_gates=("approve",))
    timeline = orch.evidence_timeline(started.run_id)
    # The timeline records the node events in order, including the publish.
    node_ids = [e["node_id"] for e in timeline if e["node_id"]]
    assert "publish" in node_ids
    assert "approve" in node_ids
    # Every entry is ordered by seq and the chain is causal.
    seqs = [e["seq"] for e in timeline]
    assert seqs == sorted(seqs)
    publish_entry = next(e for e in timeline if e["node_id"] == "publish" and e["kind"] == "workflow_node")
    assert publish_entry["caused_by"]  # publish was caused by an upstream record
