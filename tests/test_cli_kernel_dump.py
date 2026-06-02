from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_kernel_dump_reports_visible_and_blocked_capabilities() -> None:
    runner = CliRunner()

    approved = runner.invoke(app, ["kernel-dump", "--scenario", "approved-read", "--json"])
    assert approved.exit_code == 0, approved.stdout
    approved_payload = json.loads(approved.stdout)
    assert approved_payload["decision"] == "allowed"
    assert approved_payload["model_visible_capabilities"] == ["file.read"]
    assert approved_payload["blocked_capabilities"] == ["terminal.run"]
    assert approved_payload["evidence"]["status"] == "pass"

    blocked = runner.invoke(
        app,
        ["kernel-dump", "--scenario", "unapproved-terminal", "--json"],
    )
    assert blocked.exit_code == 0, blocked.stdout
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["decision"] == "blocked"
    assert blocked_payload["blocked_capabilities"] == ["terminal.run"]
    assert blocked_payload["handler_executed"] is False
    assert blocked_payload["evidence"]["status"] == "blocked"


def test_kernel_dump_rejects_malformed_authority_json() -> None:
    runner = CliRunner()
    malformed = runner.invoke(
        app,
        [
            "kernel-dump",
            "--scenario",
            "approved-read",
            "--authority-json",
            '{"principal_id":" ","run_id":"run-1","goal_contract_id":"goal-1","capability_grants":[]}',
            "--json",
        ],
    )

    assert malformed.exit_code != 0
    payload = json.loads(malformed.stdout)
    assert "principal_id" in payload["error"]
    assert payload["model_visible_capabilities"] == []
    assert payload["allowed_capabilities"] == []
