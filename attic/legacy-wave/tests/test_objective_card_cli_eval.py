from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app

runner = CliRunner()


def test_cli_objective_card_blog_demo_matches_mockup() -> None:
    result = runner.invoke(app, ["objective-card", "--demo", "blog", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "needs_answers"
    assert payload["questions"] == [
        "Where should posts publish?",
        "What is the monthly budget cap?",
    ]
    assert payload["chosen_workflow_id"] == "blog.gated"
    stages = {stage["node_id"]: stage for stage in payload["approval_stages"]}
    assert stages["publish"]["manual_approvals_remaining"] == 3
    assert payload["no_secret_echo"] is True


def test_cli_objective_card_tidy_demo_is_ready() -> None:
    result = runner.invoke(app, ["objective-card", "--demo", "tidy", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "ready_to_start"
    assert payload["blocking_question_count"] == 0


def test_cli_objective_card_missing_frame_is_blocked() -> None:
    result = runner.invoke(app, ["objective-card", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked"
    assert any("missing_frame" in reason for reason in payload["blocked_reasons"])


def test_cli_objective_card_malformed_frame_fails_closed() -> None:
    result = runner.invoke(app, ["objective-card", "--frame-json", "{\"triage\": \"nonsense\"}", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked"
    assert "malformed_objective_frame" in payload["blocked_reasons"]


def test_cli_objective_card_real_frame_json_compiles() -> None:
    frame = {
        "normalized_objective": "Summarize a doc",
        "triage": "oneshot",
        "candidates": [
            {
                "candidate_id": "summarize",
                "nodes": [
                    {"node_id": "read", "kind": "llm_generic", "produces_criteria": ["summary"]},
                    {"node_id": "check", "kind": "verification", "verifies_criteria": ["summary"]},
                ],
                "edges": [{"src": "read", "dst": "check"}],
            }
        ],
        "required_criteria": ["summary"],
    }
    result = runner.invoke(app, ["objective-card", "--frame-json", json.dumps(frame), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "ready_to_start"
    assert payload["chosen_workflow_id"] == "summarize"


def test_cli_secret_frame_blocks_and_never_echoes() -> None:
    frame = {
        "normalized_objective": "Use sk-proj-THISISSECRET to post",
        "triage": "oneshot",
        "candidates": [
            {
                "candidate_id": "c",
                "nodes": [{"node_id": "draft", "kind": "llm_generic"}],
            }
        ],
    }
    result = runner.invoke(app, ["objective-card", "--frame-json", json.dumps(frame), "--json"])
    assert result.exit_code == 0
    assert "THISISSECRET" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked_raw_secret_material"
    assert payload["no_secret_echo"] is True


def test_cli_empty_objective_frame_fails_closed() -> None:
    frame = {
        "normalized_objective": "   ",
        "triage": "oneshot",
        "candidates": [
            {"candidate_id": "c", "nodes": [{"node_id": "draft", "kind": "llm_generic"}]}
        ],
    }
    result = runner.invoke(app, ["objective-card", "--frame-json", json.dumps(frame), "--json"])
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked"
    assert "malformed_objective_frame" in payload["blocked_reasons"]
