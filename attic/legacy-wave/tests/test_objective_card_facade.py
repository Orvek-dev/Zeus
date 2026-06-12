from __future__ import annotations

from zeus_agent.library_runtime.agent import ZeusAgent


def _summarize_frame() -> dict[str, object]:
    return {
        "normalized_objective": "Summarize a doc",
        "triage": "oneshot",
        "required_criteria": ["summary"],
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
    }


def test_facade_objective_card_compiles_frame() -> None:
    payload = ZeusAgent().objective_card(_summarize_frame())
    assert payload["decision"] == "ready_to_start"
    assert payload["chosen_workflow_id"] == "summarize"
    assert payload["no_secret_echo"] is True


def test_facade_objective_card_rejects_malformed_frame() -> None:
    payload = ZeusAgent().objective_card({"triage": "nonsense"})
    assert payload["decision"] == "blocked"
    assert "malformed_objective_frame" in payload["blocked_reasons"]


def test_facade_and_cli_surfaces_match() -> None:
    from typer.testing import CliRunner
    import json

    from zeus_agent.cli import app

    facade_payload = ZeusAgent().objective_card(_summarize_frame())
    result = CliRunner().invoke(
        app, ["objective-card", "--frame-json", json.dumps(_summarize_frame()), "--json"]
    )
    cli_payload = json.loads(result.stdout)
    assert facade_payload == cli_payload
