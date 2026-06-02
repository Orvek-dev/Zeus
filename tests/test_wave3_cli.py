from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_run_command_reports_fake_local_allowed_read_completion(tmp_path: Path) -> None:
    # Given: a Wave 3 CLI runner and a prompt containing a secret-like value.
    runner = CliRunner()

    # When: the run command executes the fake local read scenario.
    result = runner.invoke(
        app,
        [
            "run",
            "--prompt",
            "read the fixture without echoing sk-test-secret",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    # Then: structured output proves fake/local-only provider, broker, and completion state.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    blob = json.dumps(payload, sort_keys=True)
    assert payload["mode"] == "run"
    assert payload["fake_local_only"] is True
    assert payload["state_home"] == str(tmp_path)
    assert str(tmp_path) in payload["sandbox_root"]
    assert payload["provider_route"]["decision"] == "selected"
    assert payload["provider_route"]["provider_id"] == "fake-local"
    assert payload["provider_route"]["local_private"] is True
    assert payload["broker_decision"]["decision"] == "allowed"
    assert payload["broker_decision"]["capability_id"] == "file.read"
    assert payload["broker_decision"]["evidence"]["status"] == "pass"
    assert payload["completion"]["status"] == "complete"
    assert payload["completion"]["verified_criteria"] == ["REQ-ZEUS-WAVE3-005:S1"]
    assert "sk-test-secret" not in blob


def test_chat_command_reports_fake_local_allowed_search_completion(tmp_path: Path) -> None:
    # Given: a Wave 3 CLI runner and a message containing a secret-like value.
    runner = CliRunner()

    # When: the chat command executes the fake local search scenario.
    result = runner.invoke(
        app,
        [
            "chat",
            "--message",
            "find needle but hide sk-chat-secret",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    # Then: structured output proves fake/local-only provider, search broker, and completion state.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    blob = json.dumps(payload, sort_keys=True)
    assert payload["mode"] == "chat"
    assert payload["fake_local_only"] is True
    assert payload["provider_route"]["decision"] == "selected"
    assert payload["provider_route"]["provider_id"] == "fake-local"
    assert payload["broker_decision"]["decision"] == "allowed"
    assert payload["broker_decision"]["capability_id"] == "text.search"
    assert payload["broker_decision"]["result"]["matches"][0]["snippet"] == "needle: wave3 searchable line"
    assert payload["completion"]["status"] == "complete"
    assert "sk-chat-secret" not in blob


def test_run_command_reports_structured_unknown_capability_block(tmp_path: Path) -> None:
    # Given: a Wave 3 CLI runner.
    runner = CliRunner()

    # When: the run command exercises the structured unknown-capability scenario.
    result = runner.invoke(
        app,
        [
            "run",
            "--prompt",
            "try unknown capability",
            "--scenario",
            "unknown-tool",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    # Then: the CLI succeeds with a policy-blocked payload instead of an unstructured crash.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["fake_local_only"] is True
    assert payload["provider_route"]["decision"] == "selected"
    assert payload["broker_decision"]["decision"] == "blocked"
    assert payload["broker_decision"]["reason"] == "unknown_capability"
    assert payload["broker_decision"]["evidence"]["status"] == "blocked"
    assert payload["completion"]["status"] == "blocked_policy"
