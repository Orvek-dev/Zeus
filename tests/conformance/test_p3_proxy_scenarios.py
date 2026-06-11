"""P3 conformance — the LLM proxy gate's named scenarios.

proxy-budget-429, tool_call-deny-injects-block, streaming-toolcall-buffer,
cost-attribution-per-objective, quota-switch-policy — exactly as frozen in
detailed-design v2, plus the fail-closed edges (responses stream rejection,
tool_call buffer overflow).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import JsonValue

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.proxy_runtime import (
    KV_LAST_REQUEST_AT,
    KV_LAST_RESPONSE_AT,
    LlmProxyEngine,
    ProxySession,
    seed_proxy_capability_store,
)
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    Reversibility,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)
from zeus_agent.wallet_runtime import QuotaSwitchRule, WalletPolicy, weekly_spend_digest

MODEL = "claude-fable-5"
ALT_MODEL = "claude-haiku-4-5"


def _quarantined(capability_id: str) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=VerbClass.publish,
        title=capability_id,
        input_summary="in",
        output_summary="out",
        side_effect=SideEffectClass.account_write,
        reversibility=Reversibility.irreversible,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.mcp,
        status=CapabilityStatus.quarantined,
    )


def _proxy(
    tmp_path: Path,
    *,
    policy: Optional[WalletPolicy] = None,
    quarantine: tuple[str, ...] = (),
) -> tuple[LlmProxyEngine, ZeusDecisionEngine, SQLiteControlPlaneStore, FlightRecorder]:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    recorder = FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))
    capabilities = seed_proxy_capability_store()
    for capability_id in quarantine:
        capabilities.register(_quarantined(capability_id))
    engine = ZeusDecisionEngine(
        recorder=recorder,
        capabilities=capabilities,
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )
    proxy = LlmProxyEngine(engine=engine, policy=policy, store=store)
    return proxy, engine, store, recorder


def _body(model: str = MODEL, content: str = "hello") -> dict[str, JsonValue]:
    return {"model": model, "messages": [{"role": "user", "content": content}]}


def _completion(
    *,
    tool_calls: Optional[list[JsonValue]] = None,
    content: Optional[str] = "done",
    usage: Optional[dict[str, JsonValue]] = None,
) -> dict[str, JsonValue]:
    message: dict[str, JsonValue] = {"role": "assistant", "content": content}
    finish = "stop"
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
        finish = "tool_calls"
    return {
        "id": "chatcmpl-up-1",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": usage or {"prompt_tokens": 100, "completion_tokens": 50},
    }


def _tool_call(call_id: str, name: str, arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


# ---------------------------------------------------------- proxy-budget-429
def test_proxy_budget_429_blocks_before_upstream(tmp_path: Path) -> None:
    proxy, _engine, store, _recorder = _proxy(tmp_path)
    store.set_budget_limit("objective", "obj.poor", 1_000)
    called = False

    def upstream(_body: dict[str, JsonValue]) -> dict[str, JsonValue]:
        nonlocal called
        called = True
        return _completion()

    session = ProxySession(objective_id="obj.poor")
    result = proxy.chat_completion(_body(), session, upstream)
    assert result.status == 429
    assert called is False, "an over-budget request must never reach the provider"
    error = result.body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "budget_exhausted_objective"
    assert str(error["message"]).startswith("[Zeus]")
    assert result.receipt_id is not None  # even a refusal leaves a receipt


def test_budget_enforcement_survives_proxy_restart(tmp_path: Path) -> None:
    first_proxy, _, store, _ = _proxy(tmp_path)
    store.set_budget_limit("objective", "obj.daily", 35_000)
    session = ProxySession(objective_id="obj.daily")
    usage = {"prompt_tokens": 1_000, "completion_tokens": 1_000}  # 30_000 units
    result = first_proxy.chat_completion(
        _body(), session, lambda _b: _completion(usage=usage)
    )
    assert result.status == 200
    assert store.budget_spent("objective", "obj.daily") == 30_000

    # a fresh proxy process over the same home must see the spend (GAP-1)
    second_proxy, _, _, _ = _proxy(tmp_path)
    denied = second_proxy.chat_completion(_body(), session, lambda _b: _completion())
    assert denied.status == 429
    error = denied.body["error"]
    assert isinstance(error, dict) and error["code"] == "budget_exhausted_objective"


# ------------------------------------------------ tool_call-deny-injects-block
def test_tool_call_deny_strips_and_injects_block(tmp_path: Path) -> None:
    proxy, engine, _store, _recorder = _proxy(
        tmp_path, quarantine=("host.tool.transfer_funds",)
    )
    upstream_response = _completion(
        content=None,
        tool_calls=[
            _tool_call("call_read", "read_file", {"path": "/work/a.py"}),
            _tool_call("call_xfer", "transfer_funds", {"amount": 100}),
        ],
    )
    session = ProxySession(session_id="sess.deny")
    result = proxy.chat_completion(_body(), session, lambda _b: upstream_response)
    assert result.status == 200
    assert result.released_tool_calls == 1
    assert result.blocked_tool_calls == 1
    assert len(result.tool_call_receipts) == 2

    choice = result.body["choices"][0]
    assert isinstance(choice, dict)
    message = choice["message"]
    assert isinstance(message, dict)
    kept = message["tool_calls"]
    assert isinstance(kept, list) and len(kept) == 1
    assert kept[0]["id"] == "call_read"
    content = str(message["content"])
    assert "[Zeus blocked: capability_quarantined]" in content
    assert "transfer_funds" in content
    # the upstream body is untouched — governance works on a copy
    assert len(upstream_response["choices"][0]["message"]["tool_calls"]) == 2

    # every receipt is in the ledger with its decision
    decisions = {
        json.loads(str(r["payload_json"])).get("capability_id"): json.loads(
            str(r["payload_json"])
        ).get("decision")
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    }
    assert decisions.get("host.tool.transfer_funds") == "deny"
    assert decisions.get("fs.read") == "auto"


def test_tool_call_ask_parks_and_injects_approval_notice(tmp_path: Path) -> None:
    proxy, engine, _store, _recorder = _proxy(tmp_path)
    upstream_response = _completion(
        content=None,
        tool_calls=[_tool_call("call_mail", "send_email", {"to": "a@b.c"})],
    )
    session = ProxySession(session_id="sess.ask")
    result = proxy.chat_completion(_body(), session, lambda _b: upstream_response)
    assert result.status == 200
    assert result.blocked_tool_calls == 1
    choice = result.body["choices"][0]
    assert isinstance(choice, dict)
    message = choice["message"]
    assert isinstance(message, dict)
    assert "tool_calls" not in message
    assert choice["finish_reason"] == "stop"  # nothing released → host stops cleanly
    content = str(message["content"])
    assert "approval required" in content
    assert "parked:" in content
    pending = engine.queue.pending(now=datetime.now(timezone.utc))
    assert len(pending) == 1
    assert pending[0].action.capability_id == "host.tool.send_email"


# ------------------------------------------------- streaming-toolcall-buffer
def _stream_chunks_fixture() -> list[dict[str, JsonValue]]:
    return [
        {
            "id": "chatcmpl-s1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        },
        {"choices": [{"index": 0, "delta": {"content": "Reading it now. "}, "finish_reason": None}]},
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_s",
                                "type": "function",
                                "function": {"name": "read_file", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"path": "/work'}}]},
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '/a.py"}'}}]},
                    "finish_reason": None,
                }
            ]
        },
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


def test_streaming_buffers_tool_call_until_decided(tmp_path: Path) -> None:
    proxy, _engine, _store, _recorder = _proxy(tmp_path)
    session = ProxySession(session_id="sess.stream")
    outcome = proxy.chat_completion_stream(
        _body(), session, lambda _b: iter(_stream_chunks_fixture())
    )
    assert outcome.error is None
    assert outcome.chunks is not None
    produced = list(outcome.chunks)

    serialized = [json.dumps(chunk) for chunk in produced]
    text_index = next(i for i, s in enumerate(serialized) if "Reading it now." in s)
    tool_indices = [i for i, chunk in enumerate(produced) if _first_tool_calls(chunk)]
    finish_index = next(
        i for i, chunk in enumerate(produced) if _finish_reason(chunk) is not None
    )

    # text passed through before any tool_call release
    assert text_index < min(tool_indices)
    # exactly ONE tool_call emission — complete, never fragmented
    assert len(tool_indices) == 1
    released = _first_tool_calls(produced[tool_indices[0]])[0]
    assert released["function"]["name"] == "read_file"
    assert json.loads(str(released["function"]["arguments"])) == {"path": "/work/a.py"}
    assert released["id"] == "call_s"
    # decision precedes the finish chunk, which keeps its meaning
    assert tool_indices[0] < finish_index
    assert _finish_reason(produced[finish_index]) == "tool_calls"


def test_streaming_blocked_tool_call_becomes_notice_and_stop(tmp_path: Path) -> None:
    proxy, _engine, _store, _recorder = _proxy(
        tmp_path, quarantine=("host.tool.transfer_funds",)
    )
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": "chatcmpl-s2",
            "object": "chat.completion.chunk",
            "created": 2,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_x",
                                "type": "function",
                                "function": {"name": "transfer_funds", "arguments": "{}"},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    assert outcome.chunks is not None
    produced = list(outcome.chunks)
    assert all(not _first_tool_calls(chunk) for chunk in produced), "blocked call must not leak"
    notice = next(s for s in (json.dumps(c) for c in produced) if "Zeus blocked" in s)
    assert "capability_quarantined" in notice
    assert _finish_reason(produced[-1]) == "stop"  # nothing released → host stops


def test_streaming_oversized_tool_call_fails_closed(tmp_path: Path) -> None:
    proxy, _engine, _store, recorder = _proxy(tmp_path)
    big = "x" * 150_000
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": "chatcmpl-s3",
            "object": "chat.completion.chunk",
            "created": 3,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_big",
                                "type": "function",
                                "function": {"name": "read_file", "arguments": big},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": big}}]},
                    "finish_reason": None,
                }
            ]
        },
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    assert outcome.chunks is not None
    produced = list(outcome.chunks)
    assert all(not _first_tool_calls(chunk) for chunk in produced)
    assert any("toolcall_buffer_overflow" in json.dumps(chunk) for chunk in produced)
    reasons = [
        json.loads(str(r["payload_json"])).get("reason")
        for r in recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    ]
    assert "toolcall_buffer_overflow" in reasons


# -------------------------------------------- cost-attribution-per-objective
def test_cost_attribution_per_objective_and_digest(tmp_path: Path) -> None:
    proxy, _engine, store, recorder = _proxy(tmp_path)
    proxy.chat_completion(
        _body(),
        ProxySession(session_id="s.a", objective_id="obj.a"),
        lambda _b: _completion(usage={"prompt_tokens": 1_000, "completion_tokens": 1_000}),
    )
    proxy.chat_completion(
        _body(),
        ProxySession(session_id="s.b", objective_id="obj.b"),
        lambda _b: _completion(usage={"prompt_tokens": 100, "completion_tokens": 100}),
    )
    assert store.budget_spent("objective", "obj.a") == 30_000  # 1k×5 + 1k×25 micro-USD
    assert store.budget_spent("objective", "obj.b") == 3_000
    assert store.budget_spent("fleet", "fleet") == 33_000

    digest = weekly_spend_digest(recorder, now=datetime.now(timezone.utc))
    assert digest["total_units"] == 33_000
    assert digest["by_objective"] == {"obj.a": 30_000, "obj.b": 3_000}
    assert digest["by_model"] == {MODEL: 33_000}
    assert digest["requests"] == 2

    # hang watchdog stamped both sides of the upstream call
    assert store.kv_get(KV_LAST_REQUEST_AT) is not None
    assert store.kv_get(KV_LAST_RESPONSE_AT) is not None


def test_secret_in_response_body_is_counted_not_mutated(tmp_path: Path) -> None:
    proxy, _engine, store, _recorder = _proxy(tmp_path)
    leaky = _completion(content="the key is ghp_FAKE_FIXTURE_TOKEN")
    result = proxy.chat_completion(_body(), ProxySession(), lambda _b: leaky)
    assert result.secret_findings >= 1
    choice = result.body["choices"][0]
    assert isinstance(choice, dict)
    message = choice["message"]
    assert isinstance(message, dict)
    # the host's view is NOT rewritten — hygiene is a scanner, not a censor
    assert message["content"] == "the key is ghp_FAKE_FIXTURE_TOKEN"
    assert int(store.kv_get("proxy.secret_findings") or 0) >= 1


# ------------------------------------------------------- quota-switch-policy
def _switch_policy() -> WalletPolicy:
    return WalletPolicy(
        rules=(
            QuotaSwitchRule(watch_model=MODEL, residual_pct_below=10.0, switch_to=ALT_MODEL),
        )
    )


def test_quota_switch_rewrites_model_with_receipt(tmp_path: Path) -> None:
    proxy, _engine, store, recorder = _proxy(tmp_path, policy=_switch_policy())
    store.set_budget_limit("objective", "obj.q", 1_000_000)
    store.add_budget_spend("objective", "obj.q", 950_000)  # residual 5% < 10%
    seen_models: list[str] = []

    def upstream(body: dict[str, JsonValue]) -> dict[str, JsonValue]:
        seen_models.append(str(body.get("model")))
        return _completion(usage={"prompt_tokens": 10, "completion_tokens": 10})

    result = proxy.chat_completion(
        _body(), ProxySession(objective_id="obj.q"), upstream
    )
    assert result.status == 200
    assert seen_models == [ALT_MODEL], "the provider must see the approved alternate"
    assert result.switched_model == ALT_MODEL
    assert result.switch_receipt_id is not None
    switch_decisions = [
        json.loads(str(r["payload_json"]))
        for r in recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
        and json.loads(str(r["payload_json"])).get("capability_id") == "llm.model_switch"
    ]
    assert len(switch_decisions) == 1
    assert switch_decisions[0]["decision"] == "auto"
    assert switch_decisions[0]["args"]["switch_to"] == ALT_MODEL


def test_quota_switch_does_not_fire_above_threshold(tmp_path: Path) -> None:
    proxy, _engine, store, _recorder = _proxy(tmp_path, policy=_switch_policy())
    store.set_budget_limit("objective", "obj.q", 1_000_000)
    store.add_budget_spend("objective", "obj.q", 100_000)  # residual 90%
    seen_models: list[str] = []

    def upstream(body: dict[str, JsonValue]) -> dict[str, JsonValue]:
        seen_models.append(str(body.get("model")))
        return _completion(usage={"prompt_tokens": 10, "completion_tokens": 10})

    result = proxy.chat_completion(_body(), ProxySession(objective_id="obj.q"), upstream)
    assert seen_models == [MODEL]
    assert result.switched_model is None


# ------------------------------------------------------------- /v1/responses
def test_responses_function_call_governed(tmp_path: Path) -> None:
    proxy, _engine, _store, _recorder = _proxy(
        tmp_path, quarantine=("host.tool.transfer_funds",)
    )
    upstream_body: dict[str, JsonValue] = {
        "id": "resp_1",
        "object": "response",
        "model": MODEL,
        "output": [
            {"type": "function_call", "call_id": "fc_1", "name": "transfer_funds", "arguments": "{}"},
            {"type": "function_call", "call_id": "fc_2", "name": "read_file", "arguments": '{"path": "/w/a"}'},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }
    result = proxy.responses(
        {"model": MODEL, "input": "go"}, ProxySession(), lambda _b: upstream_body
    )
    assert result.status == 200
    assert result.blocked_tool_calls == 1
    assert result.released_tool_calls == 1
    output = result.body["output"]
    assert isinstance(output, list)
    first = output[0]
    assert isinstance(first, dict)
    assert first["type"] == "message"
    assert "[Zeus blocked: capability_quarantined]" in json.dumps(first)
    second = output[1]
    assert isinstance(second, dict)
    assert second["type"] == "function_call" and second["name"] == "read_file"


def test_responses_stream_is_rejected_fail_closed(tmp_path: Path) -> None:
    proxy, _engine, _store, _recorder = _proxy(tmp_path)
    called = False

    def upstream(_body: dict[str, JsonValue]) -> dict[str, JsonValue]:
        nonlocal called
        called = True
        return {}

    result = proxy.responses(
        {"model": MODEL, "input": "go", "stream": True}, ProxySession(), upstream
    )
    assert result.status == 400
    assert called is False
    error = result.body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "responses_stream_not_governed"


# ---------------------------------------------------------------- helpers
def _first_tool_calls(chunk: dict[str, JsonValue]) -> list:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    choice = choices[0]
    if not isinstance(choice, dict):
        return []
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        return []
    tool_calls = delta.get("tool_calls")
    return tool_calls if isinstance(tool_calls, list) else []


def _finish_reason(chunk: dict[str, JsonValue]):
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    return choice.get("finish_reason") if isinstance(choice, dict) else None
