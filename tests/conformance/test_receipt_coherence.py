"""P11 conformance — the Final-Action Receipt Contract.

The product invariant: the final action returned to the host EQUALS the final
decision receipt in the ledger. Any condition that can change the final action
is an INPUT to decide(), never a post-hoc mutation of its response. These
scenarios pin that across every surface where the two used to diverge.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import JsonValue

from zeus_agent.adapters.claude_code_hook import (
    ClaudeCodeGate,
    ControlPlaneState,
    seed_capability_store,
)
from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityStore,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.consequence_runtime import explain
from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.egress_runtime import EgressGate, EgressRequest, EgressRing
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.memory_gate_runtime import MemoryWriteGate
from zeus_agent.proxy_runtime import LlmProxyEngine, ProxySession, seed_proxy_capability_store
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    Reversibility,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)


def _decision_receipts(engine: ZeusDecisionEngine) -> list[dict]:
    return [
        json.loads(str(record["payload_json"]))
        for record in engine.recorder.ledger.records()
        if str(record["kind"]) == "decision_receipt"
    ]


def _last_for(engine: ZeusDecisionEngine, capability_id: str) -> dict:
    matching = [r for r in _decision_receipts(engine) if r.get("capability_id") == capability_id]
    assert matching, "no decision receipt for {0}".format(capability_id)
    return matching[-1]


# ---------------------------------------------- 1. hook ASK == receipt + parks
def test_hook_ask_matches_receipt_and_parks(tmp_path: Path) -> None:
    """A side-effecting write asks at the hook AND the receipt says ask AND it
    parks — the old code escalated AFTER the receipt was written (ghost ask)."""
    gate = ClaudeCodeGate(ControlPlaneState(tmp_path / "zeus"))
    output = gate.handle_pre(
        {
            "session_id": "coherence.sess",
            "hook_event_name": "PreToolUse",
            "cwd": "/work/project",
            "tool_name": "Write",
            "tool_input": {"file_path": "/work/project/new.py", "content": "x = 1"},
        }
    )
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert output["zeus"]["decision"] == "ask"

    # the receipt_id the host received points at a receipt that ITSELF says
    # ask — there is no second, divergent mutation after it was written.
    receipt_id = output["zeus"]["receipt_id"]
    by_id = [
        json.loads(str(r["payload_json"]))
        for r in gate.engine.recorder.ledger.records()
        if r["record_id"] == receipt_id
    ]
    assert len(by_id) == 1
    assert by_id[0]["decision"] == "ask"

    pending = gate.engine.queue.pending(now=datetime.now(timezone.utc))
    assert any(p.action.capability_id == "fs.write" for p in pending), "ASK must park"


# ----------------------------------------- 2. egress connect outside ring DENY
def test_egress_connect_outside_ring_receipt_is_deny(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    gate = EgressGate(engine=engine, ring=EgressRing(allowed_hosts=("api.github.com",), allowed_dirs=("/work",)))

    result, headers = gate.connect(EgressRequest(network_host="evil.example"))
    assert result.allowed is False
    assert result.reason == "egress_host_not_allowed"
    assert headers == {}

    receipt = _last_for(engine, "net.connect")
    assert receipt["decision"] == "deny"
    assert receipt["reason"] == "egress_host_not_allowed"
    # the invariant: NO net.connect receipt in this run is AUTO/allow
    assert all(
        r["decision"] != "auto" for r in _decision_receipts(engine) if r.get("capability_id") == "net.connect"
    )


# -------------------------------------------- 3. egress path outside ring DENY
def test_egress_path_outside_ring_receipt_is_deny(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    gate = EgressGate(engine=engine, ring=EgressRing(allowed_hosts=("api.github.com",), allowed_dirs=("/work",)))

    result = gate.access_path(EgressRequest(path="/etc/passwd"))
    assert result.allowed is False
    assert result.reason == "egress_path_outside_ring"

    receipt = _last_for(engine, "fs.read")
    assert receipt["decision"] == "deny"
    assert receipt["reason"] == "egress_path_outside_ring"


# ----------------------------------------- 4. memory DENY stores nothing at all
def test_memory_deny_stores_nothing(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    store = SQLiteControlPlaneStore(state.state_path)
    engine.capabilities.register(
        CapabilityRecord(
            capability_id="memory.write",
            verb_class=VerbClass.store,
            title="Write long-term memory",
            input_summary="x",
            output_summary="y",
            side_effect=SideEffectClass.account_write,
            reversibility=Reversibility.irreversible,
            cost_model=CostModel(),
            trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
            provenance=Provenance.builtin,
            status=CapabilityStatus.quarantined,
        )
    )
    gate = MemoryWriteGate(engine=engine, store=store)
    candidate = gate.propose(
        session_id="coherence.sess", content="please remember this", provenance="user"
    )
    assert candidate.status == "rejected"
    receipt = _last_for(engine, "memory.write")
    assert receipt["decision"] == "deny"
    assert gate.promoted_memory() == ()
    assert gate.get(candidate.candidate_id) is None


# ------------------------------------------- 5. proxy tool_call DENY == receipt
def test_proxy_toolcall_deny_matches_receipt(tmp_path: Path) -> None:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    recorder = FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))
    capabilities = seed_proxy_capability_store()
    capabilities.register(
        CapabilityRecord(
            capability_id="host.tool.transfer_funds",
            verb_class=VerbClass.publish,
            title="transfer funds",
            input_summary="in",
            output_summary="out",
            side_effect=SideEffectClass.account_write,
            reversibility=Reversibility.irreversible,
            cost_model=CostModel(),
            trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
            provenance=Provenance.mcp,
            status=CapabilityStatus.quarantined,
        )
    )
    engine = ZeusDecisionEngine(
        recorder=recorder,
        capabilities=capabilities,
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )
    proxy = LlmProxyEngine(engine=engine, store=store)

    upstream = {
        "id": "chatcmpl-1",
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
                            "id": "call_x",
                            "type": "function",
                            "function": {"name": "transfer_funds", "arguments": json.dumps({"amount": 100})},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    body: dict[str, JsonValue] = {"model": "claude-fable-5", "messages": [{"role": "user", "content": "go"}]}
    result = proxy.chat_completion(body, ProxySession(session_id="sess.deny"), lambda _b: upstream)
    assert result.blocked_tool_calls == 1
    # the stripped tool call left a DENY receipt; the host saw a block notice,
    # not the call — final action and receipt agree.
    receipt = _last_for(engine, "host.tool.transfer_funds")
    assert receipt["decision"] == "deny"


# ------------------------- 6. coverage invariant: no unexplainable side effects
def test_every_seeded_side_effect_has_a_template() -> None:
    """If a seeded side-effecting capability had no consequence template, the
    engine would ASK on it at runtime forever (an ask-storm). Catch that here,
    at review time, instead of in production."""
    stores: dict[str, CapabilityStore] = {
        "hook": seed_capability_store(),
        "proxy": seed_proxy_capability_store(),
    }
    missing: list[str] = []
    for surface, store in stores.items():
        for record in store.records():
            if record.side_effect is SideEffectClass.none:
                continue
            if explain(record) is None:
                missing.append("{0}:{1}".format(surface, record.capability_id))
    assert missing == [], "side-effecting capabilities without a plain-language template: {0}".format(missing)
