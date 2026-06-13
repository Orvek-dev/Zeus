"""P9 conformance — OpenClaw adapter.

exec-approval-relay, toolcall-via-proxy-gated, clawhub-skill-onboards,
pairing-required. The v3.0.0 gate itself (≥95% on a pinned OpenClaw build +
soak) runs against the real host; these freeze the contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import JsonValue

from zeus_agent.adapters.claude_code_hook import ControlPlaneState
from zeus_agent.adapters.openclaw import (
    ExecApprovalRelay,
    openclaw_connect_bundle,
    zeus_connect_skill,
)
from zeus_agent.decision_api_runtime import HostKind
from zeus_agent.proxy_runtime import LlmProxyEngine, ProxySession, seed_proxy_capability_store
from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore


def _relay(tmp_path: Path) -> tuple[ExecApprovalRelay, list[dict[str, JsonValue]], object]:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    resolutions: list[dict[str, JsonValue]] = []
    relay = ExecApprovalRelay(engine=engine, emit=resolutions.append)
    return relay, resolutions, engine


# --------------------------------------------------------- exec-approval-relay
def test_exec_relay_allows_read_only_immediately(tmp_path: Path) -> None:
    relay, resolutions, _engine = _relay(tmp_path)
    outcome = relay.handle_approval_request(
        {"id": "req-1", "command": "ls -la", "session_id": "oc.s1"}
    )
    assert outcome["resolution"] == "allow"
    assert outcome["capability_id"] == "terminal.run.read"
    assert len(resolutions) == 1
    assert resolutions[0]["approved"] is True
    assert resolutions[0]["id"] == "req-1"
    assert resolutions[0]["decision"] == "allow-once"
    assert resolutions[0]["params"] == {"id": "req-1", "decision": "allow-once"}
    assert str(resolutions[0]["receipt_id"]).startswith("trust.ev.")


def test_exec_relay_accepts_real_openclaw_requested_event_shape(tmp_path: Path) -> None:
    relay, resolutions, _engine = _relay(tmp_path)
    outcome = relay.handle_approval_request(
        {
            "id": "req-live",
            "request": {
                "command": "ls -la",
                "sessionKey": "oc.live",
                "host": "gateway",
                "cwd": "/tmp",
            },
            "createdAtMs": 1,
            "expiresAtMs": 2,
        }
    )
    assert outcome["resolution"] == "allow"
    assert outcome["capability_id"] == "terminal.run.read"
    assert resolutions[-1]["method"] == "exec.approval.resolve"
    assert resolutions[-1]["params"] == {"id": "req-live", "decision": "allow-once"}


def test_exec_relay_parks_dangerous_until_operator(tmp_path: Path) -> None:
    relay, resolutions, engine = _relay(tmp_path)
    outcome = relay.handle_approval_request(
        {"id": "req-2", "command": "rm -rf / --no-preserve-root", "session_id": "oc.s1"}
    )
    assert outcome["resolution"] == "pending"
    parked_id = str(outcome["parked_action_id"])
    assert resolutions == [], "the agent WAITS — nothing resolves before the human"

    resolved = relay.resolve_parked(parked_id, approved=False)
    assert resolved == {"resolved": True, "status": "rejected"}
    assert len(resolutions) == 1
    assert resolutions[0]["approved"] is False
    assert resolutions[0]["decision"] == "deny"
    assert resolutions[0]["params"] == {"id": "req-2", "decision": "deny"}
    assert "operator_rejected" in str(resolutions[0]["reason"])

    # the verdict chain is in the ledger: decision receipt ← outcome record
    outcomes = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "execution_outcome"
    ]
    assert any("exec approval rejected" in str(o.get("notes", "")) for o in outcomes)


def test_exec_relay_approval_path_resolves_allow(tmp_path: Path) -> None:
    relay, resolutions, _engine = _relay(tmp_path)
    outcome = relay.handle_approval_request(
        {"id": "req-3", "command": "git push --force origin main", "session_id": "oc.s2"}
    )
    assert outcome["resolution"] == "pending"
    relay.resolve_parked(str(outcome["parked_action_id"]), approved=True)
    assert resolutions[-1]["approved"] is True


# --------------------------------- expired park never resolves approved=True
def test_expired_parked_approval_resolves_denied_to_host(tmp_path: Path) -> None:
    """TTL fail-closed end to end: even if the operator clicks approve after
    the deadline, the HOST receives approved=False — the queue's verdict wins
    over the caller's intent."""
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    store = SQLiteControlPlaneStore(state.state_path)
    emits: list[dict[str, JsonValue]] = []
    relay = ExecApprovalRelay(engine=engine, emit=emits.append, store=store)
    outcome = relay.handle_approval_request(
        {"id": "req-late", "command": "rm -rf / --no-preserve-root", "session_id": "oc.ttl"}
    )
    parked_id = str(outcome["parked_action_id"])

    # the park times out before the human answers
    from datetime import datetime, timedelta, timezone

    store.queue_expire_due((datetime.now(timezone.utc) + timedelta(seconds=601)).isoformat())

    resolved = relay.resolve_parked(parked_id, approved=True)
    assert resolved == {"resolved": True, "status": "expired"}
    assert emits, "the host still gets an answer — a denial, not silence"
    assert emits[-1]["approved"] is False
    assert emits[-1]["params"] == {"id": "req-late", "decision": "deny"}
    assert "expired" in str(emits[-1]["reason"])

    # and the ledger outcome records a failure, not a success
    outcomes = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "execution_outcome"
    ]
    assert any("exec approval expired" in str(o.get("notes", "")) for o in outcomes)


# -------------------------------------- parked ASK survives a relay restart
def test_parked_exec_approval_survives_relay_restart(tmp_path: Path) -> None:
    """A relay restart must not strand a pending host-native approval: the
    parked → request mapping is durable, so a fresh relay (sharing the store
    and a live transport) can still resolve it back to OpenClaw."""
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    store = SQLiteControlPlaneStore(state.state_path)

    first_emits: list[dict[str, JsonValue]] = []
    relay = ExecApprovalRelay(engine=engine, emit=first_emits.append, store=store)
    outcome = relay.handle_approval_request(
        {"id": "req-restart", "command": "rm -rf / --no-preserve-root", "session_id": "oc.s9"}
    )
    parked_id = str(outcome["parked_action_id"])
    assert first_emits == []  # still waiting on the human

    # the relay process dies; a NEW relay (same store, its own transport) resolves
    engine2 = ControlPlaneState(tmp_path / "zeus").build_engine(
        capabilities=seed_proxy_capability_store()
    )
    second_emits: list[dict[str, JsonValue]] = []
    relay2 = ExecApprovalRelay(
        engine=engine2, emit=second_emits.append, store=SQLiteControlPlaneStore(state.state_path)
    )
    resolved = relay2.resolve_parked(parked_id, approved=True)
    assert resolved["resolved"] is True
    assert second_emits and second_emits[-1]["approved"] is True
    assert str(second_emits[-1]["id"]) == "req-restart"

    # and it resolves exactly once — a replay finds nothing
    assert relay2.resolve_parked(parked_id, approved=True)["resolved"] is False


def test_tui_resolved_exec_approval_can_be_flushed_to_openclaw_host(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    store = SQLiteControlPlaneStore(state.state_path)

    emits: list[dict[str, JsonValue]] = []
    relay = ExecApprovalRelay(engine=engine, emit=emits.append, store=store)
    outcome = relay.handle_approval_request(
        {"id": "req-tui", "command": "git push --force origin main", "session_id": "oc.tui"}
    )
    parked_id = str(outcome["parked_action_id"])
    assert emits == []
    assert relay.flush_resolved(parked_id) == {"flushed": False, "reason": "still_pending"}

    engine.queue.resolve(parked_id, approved=True)
    after_tui = ExecApprovalRelay(engine=engine, emit=emits.append, store=store)
    assert after_tui.flush_resolved(parked_id) == {"flushed": True, "status": "approved"}
    assert emits[-1]["id"] == "req-tui"
    assert emits[-1]["approved"] is True
    assert emits[-1]["params"] == {"id": "req-tui", "decision": "allow-once"}
    assert after_tui.flush_resolved(parked_id) == {"flushed": False, "reason": "unknown_parked_action"}


# ------------------------------------------------------ toolcall-via-proxy-gated
def test_openclaw_toolcalls_gated_at_proxy_with_host_attribution(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    proxy = LlmProxyEngine(engine=engine)
    upstream = {
        "id": "c1",
        "object": "chat.completion",
        "model": "claude-fable-5",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "send_email", "arguments": "{}"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }
    session = ProxySession(session_id="oc.proxy", host=HostKind.openclaw)
    result = proxy.chat_completion(
        {"model": "claude-fable-5", "messages": [{"role": "user", "content": "go"}]},
        session,
        lambda _b: upstream,
    )
    assert result.blocked_tool_calls == 1  # no pre-hook needed — caught in-stream
    decisions = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    ]
    tool_decision = next(d for d in decisions if d.get("capability_id") == "host.tool.send_email")
    assert tool_decision["host"] == "openclaw"
    assert tool_decision["surface"] == "llm_proxy"


# ------------------------------------------- clawhub-skill-onboards / pairing
def test_clawhub_skill_onboards_with_pairing_required(tmp_path: Path) -> None:
    bundle = openclaw_connect_bundle()
    assert bundle["provider_patch"]["baseUrl"].endswith("/v1")
    assert bundle["mcp_patch"]["servers"]["zeus-gateway"]["command"] == ["zeus", "gateway"]
    assert bundle["exec_relay"]["subscribe"] == "exec.approval.requested"
    assert "zeus pair --approve" in str(bundle["pairing"]["human_step"])

    skill = zeus_connect_skill()
    assert "zeus-connect" in skill
    assert "SHOW THE CODE TO THE HUMAN" in skill
    assert "Never proceed" in skill
    assert "zeus ledger --tail" in skill
