from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.adapters.claude_code_hook import ControlPlaneState
from zeus_agent.cli_main import app
from zeus_agent.decision_api_runtime import DecisionContext, DecisionRequest, GateSurface, HostKind
from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
from zeus_agent.proxy_runtime import seed_proxy_capability_store
from zeus_agent.trust_loop_runtime import TrustDecision

runner = CliRunner()


def _decision_request(
    *,
    session_id: str,
    run_id: str,
    surface: str,
    path: str,
    defer_ask_to_owner: bool = False,
) -> str:
    return json.dumps(
        {
            "principal_id": "agent.hermes",
            "session_id": session_id,
            "run_id": run_id,
            "capability_id": "fs.write",
            "args": {"path": path},
            "context": {
                "host": "hermes",
                "surface": surface,
                "defer_ask_to_owner": defer_ask_to_owner,
            },
        }
    )


def test_hermes_hook_uses_tool_input_for_path_payload(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    hook_payload = {
        "session_id": "h.s1",
        "tool": "write_file",
        "tool_input": {"path": "/tmp/dogfood-note.txt"},
    }

    result = runner.invoke(
        app,
        ["hook", "hermes", "--home", home],
        input=json.dumps(hook_payload),
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["action"] == "block"

    pending = json.loads(runner.invoke(app, ["approvals", "--pending", "--home", home]).stdout)
    assert pending[0]["payload"] == {"path": "/tmp/dogfood-note.txt"}


def test_proxy_approval_replays_once_at_first_releasing_gate(tmp_path: Path) -> None:
    home = str(tmp_path / "zeus")
    proxy_req = _decision_request(
        session_id="llm-proxy.default",
        run_id="run.proxy.llmproxydefa",
        surface="llm_proxy",
        path="/tmp/dogfood-note.txt",
        defer_ask_to_owner=True,
    )

    asked = json.loads(runner.invoke(app, ["decide", "--request-json", proxy_req, "--home", home]).stdout)
    assert asked["decision"] == "ask"
    approved = json.loads(
        runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home]).stdout
    )
    assert approved["status"] == "approved"
    assert approved["replay"] == "approved_for_exact_payload_once"

    wrong_hook_req = _decision_request(
        session_id="20260611_154742_0066de",
        run_id="run.hermes.202606111547",
        surface="hook",
        path="/tmp/other-note.txt",
    )
    wrong_hook_retry = json.loads(
        runner.invoke(app, ["decide", "--request-json", wrong_hook_req, "--home", home]).stdout
    )
    assert wrong_hook_retry["decision"] == "ask"

    proxy_retry = json.loads(runner.invoke(app, ["decide", "--request-json", proxy_req, "--home", home]).stdout)
    assert proxy_retry["decision"] == "auto"
    assert proxy_retry["reason"] == "covered_by_replay_once"
    grants = json.loads(runner.invoke(app, ["approvals", "--home", home]).stdout)
    assert grants == []

    hook_req = _decision_request(
        session_id="20260611_154742_0066de",
        run_id="run.hermes.202606111547",
        surface="hook",
        path="/tmp/dogfood-note.txt",
    )
    hook_retry = json.loads(runner.invoke(app, ["decide", "--request-json", hook_req, "--home", home]).stdout)
    assert hook_retry["decision"] == "ask"


def test_replay_token_consumes_once_under_concurrent_proxy_retries(tmp_path: Path) -> None:
    home_path = tmp_path / "zeus"
    home = str(home_path)
    proxy_req = _decision_request(
        session_id="llm-proxy.default",
        run_id="run.proxy.llmproxydefa",
        surface="llm_proxy",
        path="/tmp/race-once.txt",
        defer_ask_to_owner=True,
    )
    asked = json.loads(runner.invoke(app, ["decide", "--request-json", proxy_req, "--home", home]).stdout)
    assert asked["decision"] == "ask"
    approved = json.loads(
        runner.invoke(app, ["approve", "--parked", asked["parked_action_id"], "--home", home]).stdout
    )
    assert approved["replay"] == "approved_for_exact_payload_once"

    request = DecisionRequest.model_validate_json(proxy_req)
    barrier = threading.Barrier(2)

    def _retry() -> str:
        engine = ControlPlaneState(home_path).build_engine(capabilities=seed_proxy_capability_store())
        barrier.wait(timeout=5)
        return engine.decide(request).reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        reasons = sorted(pool.map(lambda _idx: _retry(), range(2)))

    assert reasons.count("covered_by_replay_once") == 1
    assert len(reasons) == 2


def test_long_lived_proxy_engine_reloads_approval_grants(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    request = DecisionRequest(
        principal_id="agent.llm_proxy",
        session_id="llm-proxy.default",
        run_id="run.proxy.llmproxydefa",
        capability_id="fs.write",
        args={"path": "/tmp/dogfood-note.txt"},
        context=DecisionContext(
            host=HostKind.hermes,
            surface=GateSurface.llm_proxy,
            defer_ask_to_owner=True,
        ),
    )

    asked = engine.decide(request)
    assert asked.decision is TrustDecision.ASK

    state.add_grant(
        issue_grant(
            grant_id="grant.external.fs_write",
            capability_id="fs.write",
            scope=GrantScope.narrower,
            narrowed_paths=("/tmp/dogfood-note.txt",),
            expires_at_epoch=0,
        )
    )

    retried = engine.decide(request)
    assert retried.decision is TrustDecision.AUTO
    assert retried.reason == "covered_by_grant_narrower"
