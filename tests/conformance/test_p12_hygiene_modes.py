"""P12 conformance — proxy log-hygiene policy modes.

count (default, body untouched) | redact (mask secret spans) | block (withhold)
| ask (park for review). Any mode that mutates or withholds the body records a
decision receipt (P11 invariant), and streaming redaction reassembles a secret
split across SSE deltas before any chunk reaches the host.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import JsonValue

from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.proxy_runtime import (
    KV_HYGIENE_MODE,
    LlmProxyEngine,
    ProxySession,
    seed_proxy_capability_store,
)
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)

MODEL = "claude-fable-5"
SECRET = "sk-zeus-LIVE-7f3a9c1d2e4b6a8c0f5e1d3b7a9c2e4f"
SECRET_CORE = "7f3a9c1d2e4b6a8c0f5e1d3b7a9c2e4f"


def _proxy(tmp_path: Path, *, mode: str | None) -> tuple[LlmProxyEngine, ZeusDecisionEngine, SQLiteControlPlaneStore]:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    if mode is not None:
        store.kv_set(KV_HYGIENE_MODE, mode)
    recorder = FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))
    engine = ZeusDecisionEngine(
        recorder=recorder,
        capabilities=seed_proxy_capability_store(),
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )
    return LlmProxyEngine(engine=engine, store=store), engine, store


def _body() -> dict[str, JsonValue]:
    return {"model": MODEL, "messages": [{"role": "user", "content": "what's my key?"}]}


def _completion_with_secret() -> dict[str, JsonValue]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "sure, it is {0} — keep it safe".format(SECRET)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8},
    }


def _hygiene_receipts(engine: ZeusDecisionEngine) -> list[dict]:
    return [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
        and json.loads(str(r["payload_json"])).get("capability_id") == "llm.response.hygiene"
    ]


# ----------------------------------------------------------- count (default)
def test_count_mode_passes_body_through(tmp_path: Path) -> None:
    proxy, _engine, _store = _proxy(tmp_path, mode=None)
    result = proxy.chat_completion(_body(), ProxySession(), lambda _b: _completion_with_secret())
    assert result.status == 200
    content = result.body["choices"][0]["message"]["content"]  # type: ignore[index]
    assert SECRET in str(content), "count mode is the alpha-honest default: scan, don't mutate"
    assert result.secret_findings >= 1


# ------------------------------------------------------------------- redact
def test_redact_mode_masks_body_and_emits_receipt(tmp_path: Path) -> None:
    proxy, engine, _store = _proxy(tmp_path, mode="redact")
    result = proxy.chat_completion(_body(), ProxySession(), lambda _b: _completion_with_secret())
    assert result.status == 200
    content = str(result.body["choices"][0]["message"]["content"])  # type: ignore[index]
    assert SECRET_CORE not in content, "redact must strip the secret span"
    assert result.secret_findings >= 1
    assert result.body["zeus"]["hygiene"] == "redacted"  # type: ignore[index]

    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["decision"] == "allow"
    assert receipts[-1]["reason"].startswith("hygiene_redacted:")


# -------------------------------------------------------------------- block
def test_block_mode_withholds_response(tmp_path: Path) -> None:
    proxy, engine, _store = _proxy(tmp_path, mode="block")
    result = proxy.chat_completion(_body(), ProxySession(), lambda _b: _completion_with_secret())
    assert result.status == 403
    error = result.body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "hygiene_block"
    assert SECRET_CORE not in json.dumps(result.body), "a blocked response leaks nothing"

    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["decision"] == "deny"


# ---------------------------------------------------------------------- ask
def test_ask_mode_parks_response(tmp_path: Path) -> None:
    proxy, engine, _store = _proxy(tmp_path, mode="ask")
    result = proxy.chat_completion(_body(), ProxySession(session_id="ask.sess"), lambda _b: _completion_with_secret())
    assert result.status == 429
    error = result.body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "hygiene_ask"
    zeus = error["zeus"]
    assert isinstance(zeus, dict)
    assert zeus["parked_action_id"] is not None
    assert SECRET_CORE not in json.dumps(result.body)

    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["decision"] == "ask"


# ------------------------------------------- streaming reassembles split secret
def test_stream_redacts_cross_chunk_secret(tmp_path: Path) -> None:
    proxy, _engine, _store = _proxy(tmp_path, mode="redact")
    half = len(SECRET) // 2
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": "chatcmpl-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {"content": "your key is " + SECRET[:half]}, "finish_reason": None}],
        },
        {
            "id": "chatcmpl-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {"content": SECRET[half:] + " — done"}, "finish_reason": None}],
        },
        {
            "id": "chatcmpl-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    assert outcome.error is None
    assert outcome.chunks is not None
    produced = list(outcome.chunks)

    streamed_text = "".join(
        str(choice.get("delta", {}).get("content", ""))
        for chunk in produced
        if isinstance(chunk, dict)
        for choice in (chunk.get("choices") or [])
        if isinstance(choice, dict)
    )
    assert SECRET_CORE not in streamed_text, "a secret split across deltas must never reach the host intact"


def _content_chunk(text: str, finish: str | None = None) -> dict[str, JsonValue]:
    return {
        "id": "chatcmpl-s",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "delta": {} if text == "" else {"content": text}, "finish_reason": finish}],
    }


# ------------------------------- block/ask HOLD a stream (no silent degrade)
def test_block_mode_withholds_streaming_response(tmp_path: Path) -> None:
    proxy, engine, _store = _proxy(tmp_path, mode="block")
    chunks = [_content_chunk("your key is " + SECRET), _content_chunk("", finish="stop")]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    # the whole stream is withheld — NOT degraded to a redacted stream
    assert outcome.chunks is None
    assert outcome.error is not None
    assert outcome.error.status == 403
    assert outcome.error.body["error"]["code"] == "hygiene_block"  # type: ignore[index]
    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["decision"] == "deny"


def test_ask_mode_parks_streaming_response(tmp_path: Path) -> None:
    proxy, engine, _store = _proxy(tmp_path, mode="ask")
    chunks = [_content_chunk("token: " + SECRET), _content_chunk("", finish="stop")]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(session_id="s.ask"), lambda _b: iter(chunks))
    assert outcome.chunks is None
    assert outcome.error is not None
    assert outcome.error.status == 429
    assert outcome.error.body["error"]["zeus"]["parked_action_id"] is not None  # type: ignore[index]
    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["decision"] == "ask"


def test_block_mode_stream_buffer_is_bounded(tmp_path: Path) -> None:
    """block/ask must not buffer a stream without bound — past the cap the
    response is withheld fail-closed (same doctrine as the tool_call cap),
    with its own receipt."""
    proxy, engine, _store = _proxy(tmp_path, mode="block")
    huge = "x" * 1_200_000
    chunks = [_content_chunk(huge), _content_chunk(huge), _content_chunk("", finish="stop")]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    assert outcome.chunks is None
    assert outcome.error is not None
    assert outcome.error.status == 403
    assert outcome.error.body["error"]["code"] == "hygiene_stream_overflow"  # type: ignore[index]
    receipts = _hygiene_receipts(engine)
    assert receipts and receipts[-1]["reason"] == "hygiene_stream_overflow"


def test_block_mode_streams_clean_response(tmp_path: Path) -> None:
    proxy, _engine, _store = _proxy(tmp_path, mode="block")
    chunks = [_content_chunk("here is a clean answer"), _content_chunk("", finish="stop")]
    outcome = proxy.chat_completion_stream(_body(), ProxySession(), lambda _b: iter(chunks))
    # nothing secret → the response streams normally even under block mode
    assert outcome.error is None
    assert outcome.chunks is not None
    produced = list(outcome.chunks)
    text = "".join(
        str(choice.get("delta", {}).get("content", ""))
        for chunk in produced
        if isinstance(chunk, dict)
        for choice in (chunk.get("choices") or [])
        if isinstance(choice, dict)
    )
    assert "here is a clean answer" in text
