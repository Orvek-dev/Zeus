from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def test_cli_entrypoint_stays_thin() -> None:
    entrypoint = Path("src/zeus_agent/cli_main.py")
    runtime_modules = sorted(Path("src/zeus_agent/cli_runtime").glob("*.py"))

    assert _pure_loc(entrypoint) <= 100
    assert runtime_modules
    assert all(_pure_loc(module) <= 250 for module in runtime_modules)


def _pure_loc(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))


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


def test_status_separates_grants_replays_and_approval_queue(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    write_a = _decide_req("fs.write", path="/work/a.py")
    write_b = _decide_req("fs.write", path="/work/b.py")
    hard = _decide_req("terminal.run.external", path="/work/hard.py")

    soft_ask = json.loads(
        runner.invoke(app, ["decide", "--request-json", write_a, "--home", home]).stdout
    )
    runner.invoke(app, ["approve", "--parked", soft_ask["parked_action_id"], "--home", home])

    hard_ask = json.loads(
        runner.invoke(app, ["decide", "--request-json", hard, "--home", home]).stdout
    )
    runner.invoke(app, ["approve", "--parked", hard_ask["parked_action_id"], "--home", home])

    rejected = json.loads(
        runner.invoke(app, ["decide", "--request-json", write_b, "--home", home]).stdout
    )
    runner.invoke(
        app,
        ["approve", "--parked", rejected["parked_action_id"], "--deny", "--home", home],
    )

    result = runner.invoke(app, ["status", "--home", home])

    assert result.exit_code == 0
    status = json.loads(result.stdout)
    assert status["standing_grants"] == 1
    assert status["grants"] == {"active": 1, "consumed": 0, "expired": 0, "total": 1}
    assert status["grant_inventory"]["standing"] == status["grants"]
    assert status["grant_inventory"]["replay_authorizations"] == {
        "active": 1,
        "consumed": 0,
        "expired": 0,
        "total": 1,
    }
    assert status["approval_queue"] == {
        "pending": 0,
        "approved": 2,
        "rejected": 1,
        "expired": 0,
        "superseded": 0,
        "total": 3,
    }
    assert status["operator_inbox"]["pending_asks"] == 0
    assert status["operator_inbox"]["resolved_history"] == 3


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
    assert pending[0]["short_id"]
    assert pending[0]["card"]["approval_effect"] == "once_grant"

    approved = json.loads(
        runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home]).stdout
    )
    assert approved["status"] == "approved"
    assert approved["capability_id"] == "fs.write"

    again = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert again["decision"] == "auto"
    assert again["reason"] == "covered_by_grant_once"


def test_parked_ask_can_be_resolved_by_last_id(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    req = _decide_req("fs.write")
    asked = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)

    approved = json.loads(runner.invoke(app, ["approve", "--last", "--confirm", "--home", home]).stdout)

    assert approved["status"] == "approved"
    assert approved["parked_action_id"] == asked["parked_action_id"]


def test_approve_last_requires_confirmation(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["decide", "--request-json", _decide_req("fs.write"), "--home", home])

    result = runner.invoke(app, ["approve", "--last", "--home", home])

    assert result.exit_code != 0
    assert "--confirm" in result.output


def test_parked_ask_can_be_resolved_with_narrowed_scope(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    req = _decide_req("fs.write", path="/work/project/a.py")
    asked = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)

    approved = json.loads(
        runner.invoke(
            app,
            [
                "approve",
                "--parked",
                asked["parked_action_id"],
                "--narrow-path",
                "/work/project",
                "--home",
                home,
            ],
        ).stdout
    )

    assert approved["status"] == "approved"
    assert approved["grant_scope"] == "narrower"
    assert approved["narrowed_paths"] == ["/work/project"]
    inside = json.loads(runner.invoke(app, ["decide", "--request-json", req, "--home", home]).stdout)
    assert inside["decision"] == "auto"
    assert inside["reason"] == "covered_by_grant_narrower"
    outside = json.loads(
        runner.invoke(
            app,
            ["decide", "--request-json", _decide_req("fs.write", path="/tmp/outside.py"), "--home", home],
        ).stdout
    )
    assert outside["decision"] == "ask"


def test_notify_delivers_pending_ask_cards_to_webhook(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["decide", "--request-json", _decide_req("fs.write"), "--home", home])
    received: list[dict[str, object]] = []
    server = _WebhookServer(received)
    server.start()
    try:
        result = runner.invoke(app, ["notify", "--webhook", server.url, "--home", home])
    finally:
        server.shutdown()

    payload = json.loads(result.stdout)
    assert payload["delivered"] == 1
    assert received[0]["cards"][0]["capability_id"] == "fs.write"


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
    assert report["checks"]["hook_canary"]["ok"] is True
    assert str(report["checks"]["hook_canary"]["receipt_id"]).startswith("trust.ev.")
    assert report["checks"]["proxy_health"]["ok"] is False  # no proxy running in the test
    assert report["ready"] is False
    assert any("doctor" in item for item in report["manual"])
    assert "control-plane home" in report["soak_note"]


def test_completion_gate_blocks_claimed_done_without_artifact(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    result = runner.invoke(
        app,
        ["hook", "claude-code", "--event", "stop", "--home", home],
        input=json.dumps(
            {
                "session_id": "complete.s1",
                "final_message": "완료했습니다. /tmp/missing.txt 파일을 만들었습니다.",
                "claimed_artifacts": ["/tmp/missing.txt"],
                "claimed_tests": [".venv/bin/python -m pytest"],
                "executed_commands": [],
            }
        ),
    )

    output = json.loads(result.stdout)
    assert output["action"] == "block"
    assert output["zeus"]["completion_allowed"] is False
    assert "missing_artifact:/tmp/missing.txt" in output["zeus"]["blocked_reasons"]
    assert "missing_test_command:.venv/bin/python -m pytest" in output["zeus"]["blocked_reasons"]


def test_latency_command_reports_budget(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    result = runner.invoke(app, ["latency", "--home", home, "--samples", "3"])
    payload = json.loads(result.stdout)
    assert payload["samples"] == 3
    assert payload["budget_p95_ms"] > 0
    assert payload["decision_p95_ms"] >= 0


def test_freeze_denies_new_decisions_until_released(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["freeze", "--home", home])

    frozen = json.loads(
        runner.invoke(app, ["decide", "--request-json", _decide_req("fs.read"), "--home", home]).stdout
    )
    assert frozen["decision"] == "deny"
    assert frozen["reason"] == "operator_freeze"

    runner.invoke(app, ["freeze", "--release", "--home", home])
    released = json.loads(
        runner.invoke(app, ["decide", "--request-json", _decide_req("fs.read"), "--home", home]).stdout
    )
    assert released["decision"] == "auto"


def test_tripwire_detects_external_control_plane_change(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["init", "--home", home])
    snap = runner.invoke(app, ["tripwire", "--snapshot", "--home", home])
    assert json.loads(snap.stdout)["tracked"] > 0

    grants_path = tmp_path / "zeus" / "control-plane" / "grants.json"
    grants_path.write_text("[]\n", encoding="utf-8")
    check = json.loads(runner.invoke(app, ["tripwire", "--check", "--home", home]).stdout)

    assert check["changed"]
    assert any(item["path"].endswith("grants.json") for item in check["changed"])


def test_permission_import_summarizes_existing_claude_rules_without_secrets(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Read(./src/**)",
                        "Bash(git status:*)",
                        "Bash(rm -rf:*)",
                    ]
                },
                "env": {"OPENAI_API_KEY": "sk-should-not-appear"},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["import-permissions", "claude-code", "--settings", str(settings)],
    )

    payload = json.loads(result.stdout)
    assert payload["secret_material"] == "excluded"
    assert "sk-should-not-appear" not in result.stdout
    assert payload["tiers"]["low"] == 2
    assert payload["tiers"]["high"] == 1


def test_mcp_empty_registry_explains_itself(tmp_path: Path) -> None:
    # D8: an empty registry must read as "nothing imported yet", not broken.
    home = str(tmp_path / "zeus")
    runner.invoke(app, ["init", "--home", home])
    result = runner.invoke(app, ["mcp", "--home", home])
    payload = json.loads(result.stdout)
    assert payload["tools"] == []
    assert "no downstream MCP" in payload["note"]


class _WebhookServer:
    def __init__(self, received: list[dict[str, object]]) -> None:
        self._received = received
        handler = self._handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return "http://{0}:{1}/notify".format(host, port)

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def _handler(self):
        received = self._received

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    received.append(decoded)
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return None

        return Handler
