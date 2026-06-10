from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import __version__
from zeus_agent.cli_main import app

runner = CliRunner(mix_stderr=False)


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "zeus-agent {0}".format(__version__)


def test_product_surface_is_small() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for verb in (
        "init",
        "connect",
        "hook",
        "decide",
        "record",
        "approve",
        "approvals",
        "ledger",
        "status",
        "dev",
    ):
        assert verb in result.stdout
    # the legacy wave surface must NOT leak into the product help
    assert "wave" not in result.stdout.lower()


def test_init_creates_control_plane_home(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--home", str(tmp_path / "zeus")])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert (tmp_path / "zeus" / "control-plane").is_dir()
    assert payload["next"] == "zeus connect claude-code"


def test_hook_pre_event_round_trip(tmp_path: Path) -> None:
    payload = {
        "session_id": "sess-1",
        "tool_name": "Read",
        "tool_input": {"file_path": "/work/a.py"},
        "cwd": "/work",
    }
    result = runner.invoke(
        app,
        ["hook", "claude-code", "--home", str(tmp_path / "zeus")],
        input=json.dumps(payload),
    )
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert output["zeus"]["capability_id"] == "fs.read"


def test_hook_malformed_stdin_fails_closed_to_ask(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["hook", "claude-code", "--home", str(tmp_path / "zeus")], input="not json"
    )
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] in {"ask", "allow"}


def test_decide_and_record_round_trip(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    request = {
        "principal_id": "operator.local",
        "session_id": "sess-1",
        "run_id": "run.cli.1",
        "capability_id": "fs.read",
        "context": {"host": "console", "surface": "console"},
    }
    decided = runner.invoke(app, ["decide", "--home", home, "--request-json", json.dumps(request)])
    assert decided.exit_code == 0
    response = json.loads(decided.stdout)
    assert response["decision"] == "auto"
    recorded = runner.invoke(
        app,
        ["record", "--home", home, "--receipt", response["receipt_id"], "--status", "success"],
    )
    assert recorded.exit_code == 0
    assert json.loads(recorded.stdout)["caused_by"] == response["receipt_id"]


def test_approve_then_approvals_lists_grant(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    issued = runner.invoke(
        app,
        ["approve", "fs.write", "--home", home, "--scope", "session", "--session-id", "sess-1"],
    )
    assert issued.exit_code == 0
    listed = runner.invoke(app, ["approvals", "--home", home])
    grants = json.loads(listed.stdout)
    assert len(grants) == 1
    assert grants[0]["capability_id"] == "fs.write"


def test_status_reports_coverage_and_chain(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    payload = {
        "session_id": "sess-1",
        "tool_name": "Read",
        "tool_input": {"file_path": "/work/a.py"},
        "cwd": "/work",
    }
    runner.invoke(app, ["hook", "claude-code", "--home", home], input=json.dumps(payload))
    result = runner.invoke(app, ["status", "--home", home])
    assert result.exit_code == 0
    status = json.loads(result.stdout)
    assert status["chain_ok"] is True
    assert status["coverage"]["observed"] == 1
    assert status["decision_mix"].get("auto") == 1


def test_ledger_why_walks_chain(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    request = {
        "principal_id": "operator.local",
        "session_id": "sess-1",
        "run_id": "run.cli.2",
        "capability_id": "fs.read",
        "context": {"host": "console", "surface": "console"},
    }
    decided = json.loads(
        runner.invoke(app, ["decide", "--home", home, "--request-json", json.dumps(request)]).stdout
    )
    runner.invoke(
        app, ["record", "--home", home, "--receipt", decided["receipt_id"], "--status", "success"]
    )
    result = runner.invoke(app, ["ledger", "--home", home, "--why", decided["receipt_id"]])
    chain = json.loads(result.stdout)
    assert len(chain) == 1  # the decision receipt itself has no ancestors
    tail = runner.invoke(app, ["ledger", "--home", home, "--tail", "5"])
    assert len(json.loads(tail.stdout)) == 2


def test_connect_prints_hook_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["connect", "claude-code"])
    assert result.exit_code == 0
    config = json.loads(result.stdout)
    assert "PreToolUse" in config["hooks"]
    assert "PostToolUse" in config["hooks"]


def test_connect_write_merges_settings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}}), encoding="utf-8"
    )
    result = runner.invoke(app, ["connect", "claude-code", "--write", "--project-dir", str(project)])
    assert result.exit_code == 0
    settings = json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["allow"] == ["Bash(ls:*)"]  # untouched
    assert any(
        "zeus hook claude-code" in json.dumps(entry) for entry in settings["hooks"]["PreToolUse"]
    )
    # idempotent: second --write must not duplicate
    runner.invoke(app, ["connect", "claude-code", "--write", "--project-dir", str(project)])
    settings_again = json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert len(settings_again["hooks"]["PreToolUse"]) == 1
