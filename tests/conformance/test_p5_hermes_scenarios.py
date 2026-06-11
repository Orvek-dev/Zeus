"""P5 conformance — hermes adapter, zeusd HTTP surface, pairing, GAP-4.

hook-allow/-ask/-deny, subagent-out-of-envelope-DENY (principal threading),
pairing-required (never zero-confirm), session-recovery briefing (scoped +
ledgered + untrusted). The v2.0.0 gate itself (≥95% on a pinned hermes build
+ 7-day soak) runs against the real host; these freeze the contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zeus_agent.adapters.hermes import HermesGate
from zeus_agent.authority_compiler_runtime import (
    AuthorityEnvelope,
    GrantTier,
    GrantedCapability,
    SQLiteEnvelopeStore,
)
from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.pairing_runtime import PairingManager, sign_request
from zeus_agent.proxy_runtime import seed_proxy_capability_store
from zeus_agent.taint_runtime import TaintLabel
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)
from zeus_agent.zeusd_runtime import ZeusApiSurface


def _engine(tmp_path: Path) -> tuple[ZeusDecisionEngine, SQLiteControlPlaneStore]:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    engine = ZeusDecisionEngine(
        recorder=FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3")),
        capabilities=seed_proxy_capability_store(),
        envelopes=SQLiteEnvelopeStore(store),
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )
    return engine, store


def _envelope(objective_id: str) -> AuthorityEnvelope:
    return AuthorityEnvelope(
        envelope_id="env.{0}".format(objective_id),
        objective_id=objective_id,
        principal_id="agent.hermes",
        granted=(
            GrantedCapability(
                capability_id="fs.read", tier=GrantTier.auto, provenance="objective: read sources"
            ),
        ),
    )


# ------------------------------------------------------------- hook decisions
def test_hook_allows_read_blocks_trifecta_asks_writes(tmp_path: Path) -> None:
    engine, _store = _engine(tmp_path)
    gate = HermesGate(engine)

    allowed = gate.pre_tool_call(
        {"session_id": "h.s1", "tool": "read_file", "args": {"path": "/work/a.py"}}
    )
    assert allowed["action"] == "allow"
    assert allowed["capability_id"] == "fs.read"
    assert allowed["receipt_id"] is not None

    asked = gate.pre_tool_call(
        {"session_id": "h.s1", "tool": "write_file", "args": {"path": "/work/a.py"}}
    )
    assert asked["action"] == "ask"  # sync surface → host-native prompt (GAP-3)
    assert asked["parked_action_id"] is not None  # fail-closed TTL on our side

    # private read then external fetch = lethal-trifecta (private→external) → hard block
    engine.taint.stamp("h.s1", TaintLabel.private, "credential.read")
    blocked = gate.pre_tool_call(
        {"session_id": "h.s1", "tool": "fetch_url", "args": {"url": "https://unapproved.example/x"}}
    )
    assert blocked["action"] == "block"
    assert "private" in blocked["reason"]

    # outcomes bind back through post_tool_call
    done = gate.post_tool_call(
        {
            "session_id": "h.s1",
            "receipt_id": allowed["receipt_id"],
            "capability_id": allowed["capability_id"],
        }
    )
    assert done["recorded"] is True


# ------------------------------------------------- subagent-out-of-envelope
def test_subagent_out_of_envelope_is_denied_not_asked(tmp_path: Path) -> None:
    engine, _store = _engine(tmp_path)
    engine.envelopes.put(_envelope("obj.research"))
    gate = HermesGate(engine)

    # the coordinator itself may escalate: out-of-envelope write → ask
    parent = gate.pre_tool_call(
        {
            "session_id": "h.s2",
            "objective_id": "obj.research",
            "tool": "write_file",
            "args": {"path": "/work/out.md"},
        }
    )
    assert parent["action"] == "ask"
    assert parent["principal_id"] == "agent.hermes"

    # a child can never widen the envelope: same request as a subagent → DENY
    child = gate.pre_tool_call(
        {
            "session_id": "h.s2",
            "objective_id": "obj.research",
            "agent_id": "researcher-2",
            "parent_agent_id": "coordinator",
            "tool": "write_file",
            "args": {"path": "/work/out.md"},
        }
    )
    assert child["action"] == "block"
    assert "child_out_of_envelope" in child["reason"]
    assert child["principal_id"] == "agent.hermes.sub.researcher-2"

    # in-envelope reads still flow for the child
    child_read = gate.pre_tool_call(
        {
            "session_id": "h.s2",
            "objective_id": "obj.research",
            "agent_id": "researcher-2",
            "parent_agent_id": "coordinator",
            "tool": "read_file",
            "args": {"path": "/work/a.py"},
        }
    )
    assert child_read["action"] == "allow"


# ----------------------------------------------------------- pairing-required
def _decide_body() -> bytes:
    return json.dumps(
        {
            "principal_id": "agent.hermes",
            "session_id": "h.s3",
            "run_id": "run.hermes.s3",
            "capability_id": "fs.read",
            "context": {"host": "hermes", "surface": "hook"},
        }
    ).encode("utf-8")


def test_unpaired_decide_is_rejected_before_policy(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path)
    api = ZeusApiSurface(engine=engine, pairing=PairingManager(store))

    status, payload = api.handle("POST", "/zeus/decide", {}, _decide_body())
    assert status == 401
    error = payload["error"]
    assert isinstance(error, dict) and error["code"] == "pairing_required"
    # no decision receipt for the request itself — policy never ran
    decisions = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    ]
    assert all(d.get("capability_id") != "fs.read" for d in decisions)
    assert any(d.get("reason") == "pairing_required" for d in decisions)  # the refusal is logged


def test_paired_and_signed_decide_round_trip(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path)
    manager = PairingManager(store)
    api = ZeusApiSurface(engine=engine, pairing=manager)

    status, issued = api.handle("POST", "/zeus/pair/request", {}, b'{"host": "hermes"}')
    assert status == 200
    code, secret = str(issued["code"]), str(issued["secret"])

    body = _decide_body()
    timestamp = datetime.now(timezone.utc).isoformat()
    headers = {
        "x-zeus-pair-code": code,
        "x-zeus-timestamp": timestamp,
        "x-zeus-signature": sign_request(secret, timestamp, body),
    }
    # approved? not yet — pending pairing must still be rejected
    status, payload = api.handle("POST", "/zeus/decide", headers, body)
    assert status == 401

    assert manager.approve(code) is True
    status, decision = api.handle("POST", "/zeus/decide", headers, body)
    assert status == 200
    assert decision["decision"] == "auto"
    assert str(decision["receipt_id"]).startswith("trust.ev.")

    # record binds the outcome over HTTP too
    record_body = json.dumps(
        {"receipt_id": decision["receipt_id"], "status": "success", "cost_actual_units": 3}
    ).encode("utf-8")
    record_headers = {
        "x-zeus-pair-code": code,
        "x-zeus-timestamp": timestamp,
        "x-zeus-signature": sign_request(secret, timestamp, record_body),
    }
    status, recorded = api.handle("POST", "/zeus/record", record_headers, record_body)
    assert status == 200
    assert recorded["caused_by"] == decision["receipt_id"]

    # tampered body → bad signature → rejected
    status, _ = api.handle("POST", "/zeus/decide", headers, body + b" ")
    assert status == 401


# --------------------------------------------------- session-recovery briefing
def test_briefing_is_scoped_masked_and_tainted(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path)
    gate = HermesGate(engine)
    gate.pre_tool_call({"session_id": "h.mine", "tool": "read_file", "args": {"path": "/w/a"}})
    gate.pre_tool_call({"session_id": "h.other", "tool": "read_file", "args": {"path": "/w/b"}})

    manager = PairingManager(store)
    api = ZeusApiSurface(engine=engine, pairing=manager)
    issued = manager.request("hermes")
    manager.approve(issued["code"])
    timestamp = datetime.now(timezone.utc).isoformat()
    headers = {
        "x-zeus-pair-code": issued["code"],
        "x-zeus-timestamp": timestamp,
        "x-zeus-signature": sign_request(issued["secret"], timestamp, b""),
    }
    status, payload = api.handle(
        "GET", "/zeus/brief?session_id=h.mine&principal_id=agent.hermes", headers, b""
    )
    assert status == 200
    assert payload["taint"] == "untrusted"
    records = payload["records"]
    assert isinstance(records, list) and len(records) >= 1
    sessions = {str(record["payload"].get("session_id")) for record in records}
    assert sessions == {"h.mine"}, "an agent briefing never crosses sessions"
    assert payload["read_receipt_record_id"] is not None  # the read is itself evidence
