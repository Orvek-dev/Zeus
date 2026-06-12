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

from zeus_agent.adapters.hermes import HermesGate, hermes_connect_bundle
from zeus_agent.authority_compiler_runtime import (
    AuthorityEnvelope,
    GrantTier,
    GrantedCapability,
    SQLiteEnvelopeStore,
)
from zeus_agent.decision_api_runtime import HostKind, ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.pairing_runtime import PairingManager, sign_request
from zeus_agent.proxy_runtime import (
    LlmProxyEngine,
    ProxySession,
    seed_proxy_capability_store,
    session_from_headers,
)
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

    blocked_for_approval = gate.pre_tool_call(
        {"session_id": "h.s1", "tool": "write_file", "args": {"path": "/work/a.py"}}
    )
    assert blocked_for_approval["action"] == "block"
    assert blocked_for_approval["parked_action_id"] is not None
    assert blocked_for_approval["retry"] == "reissue_after_operator_replay_approval"

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
    assert parent["action"] == "block"
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


# ----------------------------- D2: proxy gate uses the host-aware tool catalog
def test_proxy_maps_hermes_meta_tools_without_ask_storm(tmp_path: Path) -> None:
    """The proxy intercepts tool_calls before the hermes hook runs, so a hermes
    session's read/meta tools (search_files, skills_list) must resolve through
    the hermes table to fs.read AUTO — not fall through to host.tool.* ASK."""
    engine, store = _engine(tmp_path)
    proxy = LlmProxyEngine(engine=engine, store=store)

    def _completion(tool_name: str) -> dict:
        return {
            "id": "c", "object": "chat.completion", "model": "gpt-5.4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant", "content": None,
                        "tool_calls": [
                            {"id": "t", "type": "function",
                             "function": {"name": tool_name, "arguments": "{}"}}
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        }

    body = {"model": "gpt-5.4", "messages": [{"role": "user", "content": "go"}]}
    session = ProxySession(session_id="h.proxy", host=HostKind.hermes)

    for tool in ("search_files", "skills_list", "skill_view", "todo"):
        result = proxy.chat_completion(body, session, lambda _b, t=tool: _completion(t))
        assert result.released_tool_calls == 1, "hermes read/meta tool must be released, not asked"
        assert result.blocked_tool_calls == 0

    decisions = {
        json.loads(str(r["payload_json"]))["capability_id"]
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    }
    assert "fs.read" in decisions
    assert "agent.todo.update" in decisions
    assert not any(c.startswith("host.tool.") for c in decisions), "no conservative fall-through"


# ----------------------------- D9: hook-owned host is not double-asked at proxy
def test_hook_owned_host_does_not_defer_side_effects_until_hook_block_is_proven(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path)
    # quarantine one downstream tool to prove the wall still holds
    from zeus_agent.capability_registry_runtime import (
        CapabilityRecord,
        CapabilityStatus,
        CapabilityTrust,
        CostModel,
        Provenance,
        SideEffectClass,
        VerbClass,
    )
    from zeus_agent.trust_loop_runtime import Reversibility

    engine.capabilities.register(
        CapabilityRecord(
            capability_id="host.tool.transfer_funds",
            verb_class=VerbClass.publish,
            title="transfer",
            input_summary="x",
            output_summary="y",
            side_effect=SideEffectClass.account_write,
            reversibility=Reversibility.irreversible,
            cost_model=CostModel(),
            trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
            provenance=Provenance.mcp,
            status=CapabilityStatus.quarantined,
        )
    )
    proxy = LlmProxyEngine(engine=engine, store=store, hook_owned_hosts=frozenset({HostKind.hermes}))

    def _completion(tool_name: str, args: str = "{}") -> dict:
        return {
            "id": "c", "object": "chat.completion", "model": "gpt-5.4",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "t", "type": "function",
                    "function": {"name": tool_name, "arguments": args}}]},
                "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        }

    body = {"model": "gpt-5.4", "messages": [{"role": "user", "content": "go"}]}
    session = ProxySession(session_id="h.defer", host=HostKind.hermes)

    soft = proxy.chat_completion(body, session, lambda _b: _completion("write_file", '{"path": "/w/a"}'))
    assert soft.released_tool_calls == 0
    assert soft.blocked_tool_calls == 1
    fs_write = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
        and json.loads(str(r["payload_json"])).get("capability_id") == "fs.write"
    ][-1]
    assert fs_write["decision"] == "ask"
    assert not fs_write["reason"].endswith("_deferred_to_owner")

    engine.governors.force_ask_reason = "operator_deadman"
    forced = proxy.chat_completion(body, session, lambda _b: _completion("write_file", '{"path": "/w/b"}'))
    assert forced.blocked_tool_calls == 1
    forced_write = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
        and json.loads(str(r["payload_json"])).get("reason") == "operator_deadman"
    ][-1]
    assert forced_write["decision"] == "ask"
    assert not forced_write["reason"].endswith("_deferred_to_owner")
    engine.governors.force_ask_reason = None

    # a DENY wall (quarantined tool) is NOT deferred — still stripped
    walled = proxy.chat_completion(body, session, lambda _b: _completion("transfer_funds"))
    assert walled.blocked_tool_calls == 1, "a DENY wall holds even on a hook-owned host"


# ------------------------------- D6: connect bundle matches the live hermes schema
def test_hermes_connect_bundle_emits_shell_hooks_and_named_provider() -> None:
    bundle = hermes_connect_bundle()
    patch = bundle["config_yaml_patch"]
    # named provider (not a bare base_url) so the real upstream key is passed,
    # not hermes' loopback `no-key-required` placeholder
    assert patch["providers"]["zeus"]["api"].endswith("/v1")
    assert patch["providers"]["zeus"]["key_env"] == "OPENAI_API_KEY"
    assert patch["model"]["provider"] == "zeus"
    headers = patch["model"]["default_headers"]
    assert headers["x-zeus-host"] == "hermes"
    assert session_from_headers(headers).host is HostKind.hermes
    # SHELL hooks (a list of {command}), the schema hermes v0.16.x accepts
    pre = patch["hooks"]["pre_tool_call"]
    assert isinstance(pre, list) and pre[0]["command"] == "zeus hook hermes --event pre"
    post = patch["hooks"]["post_tool_call"]
    assert post[0]["command"] == "zeus hook hermes --event post"
    assert "zeus pair --approve" in str(bundle["pairing"]["human_step"])
    assert "--hook-owned-host hermes" in str(bundle["proxy_note"])
