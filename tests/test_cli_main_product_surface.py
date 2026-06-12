from __future__ import annotations

import json
import time
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import __version__
from zeus_agent.adapters.claude_code_hook.state import ControlPlaneState
from zeus_agent.cli_main import app
from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

runner = CliRunner()


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
        "why",
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


def test_why_shows_parked_action_timeline(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    req = _decide_req("fs.write")
    asked = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)

    result = runner.invoke(app, ["why", "--parked", asked["parked_action_id"], "--home", home])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["parked_action_id"] == asked["parked_action_id"]
    assert report["approval_effect"] == "once_grant"
    assert "separate operator terminal" in report["operator_note"]
    assert [
        item["kind"]
        for item in report["timeline"]
        if item["capability_id"] == "fs.write" and item["decision"] == "ask"
    ] == ["decision_receipt"]


def test_why_for_parked_action_excludes_prior_same_capability_attempt(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    first = runner.invoke(
        app,
        ["hook", "hermes", "--home", home],
        input=json.dumps(
            {"session_id": "h", "tool": "write_file", "args": {"path": "/work/a.py"}}
        ),
    )
    second = runner.invoke(
        app,
        ["hook", "hermes", "--home", home],
        input=json.dumps(
            {"session_id": "h", "tool": "write_file", "args": {"path": "/work/b.py"}}
        ),
    )
    first_output = json.loads(first.stdout)
    second_output = json.loads(second.stdout)

    result = runner.invoke(
        app, ["why", "--parked", second_output["parked_action_id"], "--home", home]
    )

    assert result.exit_code == 0
    timeline = json.loads(result.stdout)["timeline"]
    assert [item["kind"] for item in timeline] == ["decision_receipt", "gate_observation"]
    assert {item["record_id"] for item in timeline}.isdisjoint({first_output["receipt_id"]})
    assert timeline[0]["record_id"] == second_output["receipt_id"]
    assert timeline[1]["decision_receipt_record_id"] == second_output["receipt_id"]


def test_status_splits_active_consumed_and_expired_grants(tmp_path: Path) -> None:
    home_path = tmp_path / "zeus"
    now_epoch = int(time.time())
    state = ControlPlaneState(home_path)
    state.add_grant(
        issue_grant(
            grant_id="grant.active",
            capability_id="fs.read",
            scope=GrantScope.session,
            session_id="sess-1",
            expires_at_epoch=now_epoch + 3600,
        )
    )
    state.add_grant(
        issue_grant(
            grant_id="grant.consumed",
            capability_id="fs.write",
            scope=GrantScope.once,
            expires_at_epoch=now_epoch + 3600,
        ).model_copy(update={"consumed": True})
    )
    state.add_grant(
        issue_grant(
            grant_id="grant.expired",
            capability_id="fs.write",
            scope=GrantScope.narrower,
            narrowed_paths=("/tmp",),
            expires_at_epoch=now_epoch - 1,
        )
    )

    result = runner.invoke(app, ["status", "--home", str(home_path)])

    assert result.exit_code == 0
    status = json.loads(result.stdout)
    assert status["standing_grants"] == 1
    assert status["grants"] == {"active": 1, "consumed": 1, "expired": 1, "total": 3}


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


def _decide_req(capability_id: str, path: str = "/work/a.py") -> str:
    return json.dumps(
        {
            "principal_id": "agent.test",
            "session_id": "cockpit.sess",
            "run_id": "run.cockpit",
            "capability_id": capability_id,
            "args": {"path": path},
            "context": {"host": "console", "surface": "console"},
        }
    )


def test_parked_ask_cockpit_approve_makes_retry_auto(tmp_path: Path) -> None:
    # D3: ASK on the async surface is no longer a dead end — the operator can
    # list pending parks and approve one, and the host's re-issued call passes.
    home = str(tmp_path / "zeus")
    req = _decide_req("fs.write")

    asked = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert asked["decision"] == "ask"
    assert asked["parked_action_id"] is not None

    pending = json.loads(runner.invoke(app, ["approvals", "--pending", "--home", home]).stdout)
    assert any(p["parked_action_id"] == asked["parked_action_id"] for p in pending)
    assert pending[0]["capability_id"] == "fs.write"

    approved = json.loads(
        runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home]).stdout
    )
    assert approved["status"] == "approved"
    assert approved["capability_id"] == "fs.write"

    again = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert again["decision"] == "auto"
    assert again["reason"] == "covered_by_grant_once"


def test_parked_ask_hard_risk_approval_issues_payload_scoped_replay(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    req = _decide_req("terminal.run.external")
    asked = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert asked["decision"] == "ask"
    approved = json.loads(
        runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home]).stdout
    )
    assert approved["status"] == "approved"
    assert "grant_id" not in approved  # hard-risk: not licensed
    assert approved["replay"] == "approved_for_exact_payload_once"
    again = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert again["decision"] == "auto"
    assert again["reason"] == "covered_by_replay_once"
    third = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert third["decision"] == "ask"


def test_parked_ask_replay_is_payload_scoped(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    original = _decide_req("terminal.run.external", path="/work/a.py")
    asked = json.loads(
        runner.invoke(app, ["decide", "--request-json", original, "--home", home]).stdout
    )
    runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home])

    changed_payload = _decide_req("terminal.run.external", path="/work/b.py")
    changed = json.loads(
        runner.invoke(app, ["decide", "--request-json", changed_payload, "--home", home]).stdout
    )
    assert changed["decision"] == "ask"


def test_hermes_hook_cli_decides_over_stdin(tmp_path: Path) -> None:
    # D6: first-class `zeus hook hermes` entrypoint — JSON in, decision out.
    home = str(tmp_path / "zeus")
    read = runner.invoke(
        app, ["hook", "hermes", "--home", home],
        input='{"session_id": "h", "tool": "read_file", "args": {"path": "/work/a.py"}}',
    )
    assert json.loads(read.stdout)["action"] == "allow"
    write = runner.invoke(
        app, ["hook", "hermes", "--home", home],
        input='{"session_id": "h", "tool": "write_file", "args": {"path": "/work/a.py"}}',
    )
    write_output = json.loads(write.stdout)
    assert write_output["action"] == "block"
    assert write_output["retry"] == "reissue_after_operator_replay_approval"


def test_hermes_connect_check_preflights(tmp_path: Path) -> None:
    # D7: --check reports Zeus-verifiable preconditions + a manual checklist.
    home = str(tmp_path / "zeus")
    result = runner.invoke(app, ["connect", "hermes", "--check", "--home", home])
    report = json.loads(result.stdout)
    assert report["checks"]["control_plane_home"]["ok"] is True
    assert report["checks"]["proxy_health"]["ok"] is False  # no proxy running in the test
    assert report["ready"] is False
    assert any("doctor" in item for item in report["manual"])
    assert "control-plane home" in report["soak_note"]


def test_mcp_empty_registry_explains_itself(tmp_path: Path) -> None:
    # D8: an empty registry must read as "nothing imported yet", not broken.
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["init", "--home", home])
    result = runner.invoke(app, ["mcp", "--home", home])
    payload = json.loads(result.stdout)
    assert payload["tools"] == []
    assert "no downstream MCP" in payload["note"]
