from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.graded_approval_runtime import GrantScope, grant_covers, issue_grant
from zeus_agent.kill_switch_runtime import KillSwitch
from zeus_agent.status_cockpit_runtime import SurfaceStatus, build_status
from zeus_agent.welcome_runtime import build_welcome, render_text

runner = CliRunner()


# --- Kill switch ------------------------------------------------------------


def test_kill_switch_global_blocks_everything() -> None:
    ks = KillSwitch()
    assert ks.is_blocked(run_id="r", capability_id="c") is None
    ks.engage_global()
    assert ks.is_blocked(run_id="r", capability_id="c") == "kill_switch_global"
    ks.release_global()
    assert ks.is_blocked(run_id="r", capability_id="c") is None


def test_kill_switch_revokes_run_and_capability() -> None:
    ks = KillSwitch()
    ks.revoke_run("run.x")
    ks.revoke_capability("mcp.evil.tool")
    assert ks.is_blocked(run_id="run.x") == "run_revoked"
    assert ks.is_blocked(capability_id="mcp.evil.tool") == "capability_revoked"
    assert ks.is_blocked(run_id="run.y", capability_id="ok") is None
    assert len(ks.receipts()) == 2


def test_kill_switch_halts_a_run_in_flight(tmp_path) -> None:
    # An engaged switch must stop the executor at the next node.
    from datetime import datetime, timedelta, timezone

    from zeus_agent.kernel.capabilities import (
        CapabilityDescriptor, CapabilityGraph, CapabilityRisk,
    )
    from zeus_agent.runtime_lease import RuntimeLease
    from zeus_agent.trust_loop_runtime import GovernedExecutionDispatcher, SQLiteEvidenceLedger
    from zeus_agent.workflow_execution_runtime import (
        RunStatus, WorkflowExecutionRuntime, WorkflowExecutionStateStore,
    )
    from zeus_agent.workflow_fabric_runtime import (
        NodeKind, WorkflowCandidate, WorkflowEdge, WorkflowNode,
    )

    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    descriptor = CapabilityDescriptor(
        capability_id="x.cap", name="x_cap", risk=CapabilityRisk.low,
        input_schema={"type": "object"}, output_schema={"type": "object"},
    )
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=CapabilityGraph((descriptor,)), handlers={"x.cap": lambda _p: {"ok": True}},
        ledger=ledger,
    )
    ks = KillSwitch()
    ks.engage_global()
    runtime = WorkflowExecutionRuntime(
        dispatcher=dispatcher, ledger=ledger,
        state_store=WorkflowExecutionStateStore(tmp_path / "runs.sqlite3"), kill_switch=ks,
    )
    candidate = WorkflowCandidate(
        candidate_id="c",
        nodes=(WorkflowNode(node_id="a", kind=NodeKind.llm_generic),
               WorkflowNode(node_id="b", kind=NodeKind.llm_generic)),
        edges=(WorkflowEdge(src="a", dst="b"),),
    )
    now = datetime.now(timezone.utc)
    lease = RuntimeLease(
        lease_id="l", objective_id="o", principal_id="operator.local", run_id="run.k",
        allowed_capabilities=("x.cap",), credential_scopes=(), network_hosts=(), budget_limit=10,
        evidence_target="mneme.workflow_execution", live_transport_allowed=True,
        issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(minutes=10),
    )
    run = runtime.start(candidate, lease=lease, objective_id="o")
    assert run.status is RunStatus.blocked
    assert run.blocked_reason == "revoked:kill_switch_global"


# --- Graded approval --------------------------------------------------------


def test_once_grant_covers_a_single_capability() -> None:
    grant = issue_grant(grant_id="g1", capability_id="sandbox.fs.write", scope=GrantScope.once)
    assert grant_covers(grant, capability_id="sandbox.fs.write", now_epoch=100) is True
    assert grant_covers(grant, capability_id="other.cap", now_epoch=100) is False


def test_session_grant_expires() -> None:
    grant = issue_grant(grant_id="g2", capability_id="cap", scope=GrantScope.session,
                        session_id="s1", expires_at_epoch=200)
    assert grant_covers(grant, capability_id="cap", now_epoch=150, session_id="s1") is True
    assert grant_covers(grant, capability_id="cap", now_epoch=250, session_id="s1") is False
    assert grant_covers(grant, capability_id="cap", now_epoch=150, session_id="other") is False


def test_standing_grant_never_covers_hard_risk() -> None:
    grant = issue_grant(grant_id="g3", capability_id="cap", scope=GrantScope.session, session_id="s1")
    assert grant.covers_hard_risk is False
    assert grant_covers(grant, capability_id="cap", now_epoch=10, session_id="s1", hard_risk=True) is False


def test_narrower_grant_requires_path_inside_scope() -> None:
    grant = issue_grant(grant_id="g4", capability_id="cap", scope=GrantScope.narrower,
                        session_id="s1", narrowed_paths=("/repo/src",))
    assert grant_covers(grant, capability_id="cap", now_epoch=10, session_id="s1", path="/repo/src/a.py") is True
    assert grant_covers(grant, capability_id="cap", now_epoch=10, session_id="s1", path="/etc/passwd") is False


# --- Status cockpit ---------------------------------------------------------


def test_status_cockpit_is_honest_about_blocked_surfaces() -> None:
    report = build_status((
        SurfaceStatus(surface="provider", ready=True, detail="fake vendor ready"),
        SurfaceStatus(surface="browser", ready=False, detail="not wired (gap node)"),
    ))
    assert report.ready_count == 1
    assert report.blocked_count == 1
    # Not every surface is ready → never claims production-live.
    assert report.production_live_claimed is False


def test_status_cockpit_claims_live_only_when_all_ready() -> None:
    report = build_status((SurfaceStatus(surface="provider", ready=True, detail="ok"),))
    assert report.production_live_claimed is True


# --- Welcome screen ---------------------------------------------------------


def test_welcome_render_has_pillars_and_honest_mode() -> None:
    screen = build_welcome(version="v6.1.0")
    text = render_text(screen)
    assert "ZEUS  v6.1.0" in text
    assert "objective" in text and "authority" in text and "evidence" in text
    assert "dry-run" in text
    assert "not connected" in text


def test_cli_welcome_json_and_text() -> None:
    json_result = runner.invoke(app, ["welcome", "--json"])
    assert json_result.exit_code == 0
    payload = json.loads(json_result.stdout)
    assert payload["tagline"] == "governed objective runtime"

    text_result = runner.invoke(app, ["welcome"])
    assert text_result.exit_code == 0
    assert "zeus ›" in text_result.stdout
