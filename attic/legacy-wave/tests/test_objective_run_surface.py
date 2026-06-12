from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime.agent import ZeusAgent

runner = CliRunner()

_FRAME = {
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


def test_cli_objective_run_suspends_then_resumes_to_completion(tmp_path) -> None:
    # Start: suspends at the gate.
    start = runner.invoke(
        app, ["objective-run", "--frame-output", json.dumps(_FRAME), "--home", str(tmp_path), "--json"]
    )
    assert start.exit_code == 0
    started = json.loads(start.stdout)
    assert started["stage"] == "waiting_approval"

    # Resume by approving the gate → completes.
    resumed_run = runner.invoke(
        app,
        ["objective-run", "--frame-output", json.dumps(_FRAME), "--home", str(tmp_path),
         "--approve-gates", "approve", "--json"],
    )
    payload = json.loads(resumed_run.stdout)
    assert payload["stage"] == "completed"
    assert payload["run"]["node_states"]["publish"] == "succeeded"


def test_facade_objective_run_end_to_end(tmp_path) -> None:
    agent = ZeusAgent(home=tmp_path)
    started = agent.objective_run(_FRAME)
    assert started["stage"] == "waiting_approval"
    completed = agent.objective_run(_FRAME, approve_gates=("approve",))
    assert completed["stage"] == "completed"


def test_facade_objective_run_rejects_malformed_frame(tmp_path) -> None:
    result = ZeusAgent(home=tmp_path).objective_run({"triage": "nonsense"})
    assert result["stage"] == "blocked"
    assert "malformed_objective_frame" in result["blocked_reasons"]
