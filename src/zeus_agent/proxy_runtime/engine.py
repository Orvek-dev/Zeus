from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from itertools import chain
from typing import Any, Callable, Final, Iterator, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    DecisionResponse,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.security.credentials import contains_secret_material
from zeus_agent.taint_runtime import (
    SessionTaintTracker,
    TaintLabel,
    is_private_source,
    is_untrusted_source,
)
from zeus_agent.trust_loop_runtime import (
    BudgetEnvelope,
    ExecutionOutcome,
    ExecutionStatus,
    SQLiteControlPlaneStore,
    TrustDecision,
    TrustLoopAction,
)
from zeus_agent.wallet_runtime import CostMeter, WalletPolicy

from .hygiene import (
    HygieneMode,
    RollingRedactor,
    hygiene_mode_of,
    redact_chat_body,
    redact_responses_body,
)
from .mapping import map_tool_call_for_host

_RELEASED_DECISIONS: Final = {TrustDecision.AUTO, TrustDecision.NOTIFY}
# A tool_call fragment buffer past this size is hostile or broken; the call is
# blocked fail-closed rather than released unexamined.
_TOOLCALL_BUFFER_CAP: Final = 200_000
_HYGIENE_SCAN_CAP: Final = 1_000_000
# block/ask hygiene must buffer a whole stream before deciding; a stream past
# this many buffered characters is withheld fail-closed instead of buffered
# without bound (memory/latency hostage by a hostile or runaway upstream).
_STREAM_BUFFER_CAP: Final = 2_000_000

# Sentinel: the upstream stream opened cleanly but yielded nothing.
_STREAM_EXHAUSTED: Final = object()

KV_LAST_REQUEST_AT: Final = "proxy.last_request_at"
KV_LAST_RESPONSE_AT: Final = "proxy.last_response_at"
KV_SECRET_FINDINGS: Final = "proxy.secret_findings"

Upstream = Callable[[dict[str, JsonValue]], dict[str, JsonValue]]
UpstreamStream = Callable[[dict[str, JsonValue]], Iterator[dict[str, JsonValue]]]


class ProxySession(BaseModel):
    """Who this request runs as — attached from the session map (headers)."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    principal_id: str = "agent.llm_proxy"
    session_id: str = "llm-proxy.default"
    objective_id: Optional[str] = None
    host: HostKind = HostKind.console
    run_id: Optional[str] = None

    def resolved_run_id(self) -> str:
        if self.run_id is not None and self.run_id.strip():
            return self.run_id
        cleaned = "".join(ch for ch in self.session_id if ch.isalnum())
        return "run.proxy.{0}".format((cleaned[:12] or "default").lower())


class ProxyHttpResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    status: int
    body: dict[str, JsonValue]
    receipt_id: Optional[str] = None
    tool_call_receipts: tuple[str, ...] = ()
    blocked_tool_calls: int = 0
    released_tool_calls: int = 0
    secret_findings: int = 0
    switched_model: Optional[str] = None
    switch_receipt_id: Optional[str] = None


class StreamOutcome:
    """Either an immediate refusal (error) or a governed chunk iterator."""

    def __init__(
        self,
        *,
        error: Optional[ProxyHttpResult] = None,
        chunks: Optional[Iterator[dict[str, JsonValue]]] = None,
    ) -> None:
        self.error = error
        self.chunks = chunks


class _ToolCallEntry:
    __slots__ = ("call_id", "name", "arguments", "released", "overflow")

    def __init__(self) -> None:
        self.call_id: Optional[str] = None
        self.name = ""
        self.arguments = ""
        self.released = False
        self.overflow = False


class LlmProxyEngine:
    """Gate 1 — the LLM proxy's two decision points (P3).

    1. request ingress: pre-call budget enforcement; over budget is an HTTP
       429 with a Zeus reason, never a silent truncation.
    2. response egress: every tool_call the model emits is decided before the
       host ever sees it; a denied call is stripped and replaced with a
       "[Zeus blocked: ...]" notice so the model re-plans.

    Transport-agnostic: upstream I/O is an injected callable, so conformance
    runs without sockets and the stdlib HTTP server stays a thin shell.
    """

    def __init__(
        self,
        *,
        engine: ZeusDecisionEngine,
        meter: Optional[CostMeter] = None,
        policy: Optional[WalletPolicy] = None,
        store: Optional[SQLiteControlPlaneStore] = None,
        persist_taint: Optional[Callable[[SessionTaintTracker, tuple[str, ...]], None]] = None,
        hook_owned_hosts: frozenset[HostKind] = frozenset(),
    ) -> None:
        self.engine = engine
        self.meter = meter if meter is not None else CostMeter()
        self.policy = policy if policy is not None else WalletPolicy()
        self.store = store
        self._persist_taint = persist_taint
        # D9: hosts whose own blocking pre_tool_call hook owns the synchronous
        # ASK. For these, the proxy's tool_call gate defers a SOFT ask to the
        # hook (no double prompt) but still records + still enforces DENY walls.
        # Opt-in: only set when that hook is actually configured and live.
        self._hook_owned_hosts = hook_owned_hosts

    # ------------------------------------------------------------ /v1/models
    def models(self) -> ProxyHttpResult:
        data: list[JsonValue] = [
            {"id": model_id, "object": "model", "owned_by": "upstream"}
            for model_id in sorted(self.meter.table.prices)
        ]
        return ProxyHttpResult(status=200, body={"object": "list", "data": data})

    # -------------------------------------------------- /v1/chat/completions
    def chat_completion(
        self,
        body: dict[str, JsonValue],
        session: ProxySession,
        upstream: Upstream,
    ) -> ProxyHttpResult:
        # switch first: the pre-call budget check must price the model that
        # will actually run, or quota pressure could never be relieved.
        sent_body, switched_to, switch_receipt = self._maybe_switch_model(body, session)
        ingress = self._ingress_decide(sent_body, session)
        if ingress.decision not in _RELEASED_DECISIONS:
            return self._refusal(ingress)
        response_body, failure = self._call_upstream(upstream, sent_body, ingress, session)
        if failure is not None:
            return failure
        governed, receipts, blocked, released = self._govern_choices_tool_calls(
            response_body if response_body is not None else {}, session
        )
        governed, findings, refusal = self._hygiene_apply(governed, session, kind="chat")
        actual = self.meter.actual_units(
            str(sent_body.get("model", "")), _usage_of(governed)
        )
        # the upstream generation already cost money even when hygiene withholds
        # the body — record the spend, then surface the hygiene refusal if any.
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                cost_actual_units=actual if actual > 0 else self.meter.estimate_request_units(sent_body),
                notes="llm_proxy chat.completions",
            ),
        )
        if refusal is not None:
            return refusal
        return ProxyHttpResult(
            status=200,
            body=governed,
            receipt_id=ingress.receipt_id,
            tool_call_receipts=receipts,
            blocked_tool_calls=blocked,
            released_tool_calls=released,
            secret_findings=findings,
            switched_model=switched_to,
            switch_receipt_id=switch_receipt,
        )

    def chat_completion_stream(
        self,
        body: dict[str, JsonValue],
        session: ProxySession,
        upstream_stream: UpstreamStream,
    ) -> StreamOutcome:
        sent_body, _switched_to, _switch_receipt = self._maybe_switch_model(body, session)
        ingress = self._ingress_decide(sent_body, session)
        if ingress.decision not in _RELEASED_DECISIONS:
            return StreamOutcome(error=self._refusal(ingress))
        mode = hygiene_mode_of(self.store)
        if mode in {HygieneMode.block, HygieneMode.ask}:
            # a stream can't be un-sent: block/ask must decide on the WHOLE
            # response before emitting anything, so buffer upstream fully and
            # withhold/park if it carries a secret (no silent degrade to redact).
            return self._stream_buffered_hygiene(sent_body, session, upstream_stream, ingress, mode)
        redactor = RollingRedactor() if mode is HygieneMode.redact else None
        # D1: open the upstream BEFORE the server commits 200 + SSE headers, so
        # an upstream error becomes a governed 502 + failure outcome — never an
        # empty "200 text/event-stream" the host reads as a silent truncation.
        self._stamp(KV_LAST_REQUEST_AT)
        try:
            first_chunk, upstream_iter = _open_upstream(upstream_stream, sent_body)
        except Exception as exc:  # provider/network failure on connect
            return StreamOutcome(error=self._stream_upstream_error(ingress, exc))
        if first_chunk is _STREAM_EXHAUSTED:
            return StreamOutcome(error=self._stream_empty_error(ingress))
        return StreamOutcome(
            chunks=self._stream_chunks(
                sent_body, session, ingress, redactor, first_chunk, upstream_iter
            )
        )

    def _stream_upstream_error(self, ingress: DecisionResponse, exc: Exception) -> ProxyHttpResult:
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.error,
                notes="llm_proxy stream upstream error: {0}".format(exc),
            ),
        )
        return ProxyHttpResult(
            status=502,
            body=_error_body(
                "[Zeus] upstream provider error: {0}".format(exc), code="upstream_error"
            ),
            receipt_id=ingress.receipt_id,
        )

    def _stream_empty_error(self, ingress: DecisionResponse) -> ProxyHttpResult:
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.error,
                notes="llm_proxy stream upstream error: empty stream",
            ),
        )
        return ProxyHttpResult(
            status=502,
            body=_error_body("[Zeus] upstream provider error: empty stream", code="upstream_empty_stream"),
            receipt_id=ingress.receipt_id,
        )

    # --------------------------------------------------------- /v1/responses
    def responses(
        self,
        body: dict[str, JsonValue],
        session: ProxySession,
        upstream: Upstream,
    ) -> ProxyHttpResult:
        if bool(body.get("stream")):
            # Fail closed and visibly: an ungoverned stream is not an option,
            # a silently downgraded one is a lie. Chat completions stream fine.
            return ProxyHttpResult(
                status=400,
                body=_error_body(
                    "[Zeus] /v1/responses streaming is not yet governed; "
                    "retry with stream=false or use /v1/chat/completions",
                    code="responses_stream_not_governed",
                ),
            )
        sent_body, switched_to, switch_receipt = self._maybe_switch_model(body, session)
        ingress = self._ingress_decide(sent_body, session)
        if ingress.decision not in _RELEASED_DECISIONS:
            return self._refusal(ingress)
        response_body, failure = self._call_upstream(upstream, sent_body, ingress, session)
        if failure is not None:
            return failure
        governed, receipts, blocked, released = self._govern_output_items(
            response_body if response_body is not None else {}, session
        )
        governed, findings, refusal = self._hygiene_apply(governed, session, kind="responses")
        actual = self.meter.actual_units(str(sent_body.get("model", "")), _usage_of(governed))
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                cost_actual_units=actual if actual > 0 else self.meter.estimate_request_units(sent_body),
                notes="llm_proxy responses",
            ),
        )
        if refusal is not None:
            return refusal
        return ProxyHttpResult(
            status=200,
            body=governed,
            receipt_id=ingress.receipt_id,
            tool_call_receipts=receipts,
            blocked_tool_calls=blocked,
            released_tool_calls=released,
            secret_findings=findings,
            switched_model=switched_to,
            switch_receipt_id=switch_receipt,
        )

    # ----------------------------------------------------------- decision #1
    def _ingress_decide(
        self, body: dict[str, JsonValue], session: ProxySession
    ) -> DecisionResponse:
        estimated = self.meter.estimate_request_units(body)
        request = DecisionRequest(
            principal_id=session.principal_id,
            session_id=session.session_id,
            run_id=session.resolved_run_id(),
            capability_id="llm.generate",
            args={"model": str(body.get("model", "")), "estimated_units": estimated},
            requested_units=estimated,
            context=DecisionContext(
                host=session.host,
                surface=GateSurface.llm_proxy,
                objective_id=session.objective_id,
            ),
        )
        response = self.engine.decide(request)
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id,
            host=session.host.value,
            surface=GateSurface.llm_proxy.value,
            capability_id="llm.generate",
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        return response

    def _refusal(self, response: DecisionResponse) -> ProxyHttpResult:
        if response.decision is TrustDecision.DENY:
            status = 429 if response.reason.startswith("budget_exhausted") else 403
            message = "[Zeus] denied: {0}".format(response.reason)
        else:  # ASK on the async proxy surface parks in the Zeus queue
            status = 429
            message = (
                "[Zeus] approval required: {0} (parked: {1}); "
                "operator resolves this in Zeus control tower or a separate terminal, "
                "then re-issue the same request".format(
                    response.reason, response.parked_action_id
                )
            )
        body = _error_body(
            message,
            code=response.reason,
            receipt_id=response.receipt_id,
            parked_action_id=response.parked_action_id,
        )
        return ProxyHttpResult(status=status, body=body, receipt_id=response.receipt_id)

    # ----------------------------------------------------------- quota switch
    def _maybe_switch_model(
        self, body: dict[str, JsonValue], session: ProxySession
    ) -> tuple[dict[str, JsonValue], Optional[str], Optional[str]]:
        model = str(body.get("model", ""))
        rule = self.policy.rule_for(model)
        if rule is None or self.store is None:
            return body, None, None
        scope, scope_id = (
            ("objective", session.objective_id)
            if session.objective_id is not None
            else ("fleet", "fleet")
        )
        limit = self.store.budget_limit(scope, scope_id)
        if limit is None or limit <= 0:
            return body, None, None
        residual_pct = max(limit - self.store.budget_spent(scope, scope_id), 0) * 100.0 / limit
        if residual_pct >= rule.residual_pct_below:
            return body, None, None
        switch_request = DecisionRequest(
            principal_id=session.principal_id,
            session_id=session.session_id,
            run_id=session.resolved_run_id(),
            capability_id="llm.model_switch",
            args={
                "model": model,
                "switch_to": rule.switch_to,
                "residual_pct": round(residual_pct, 2),
            },
            context=DecisionContext(
                host=session.host,
                surface=GateSurface.llm_proxy,
                objective_id=session.objective_id,
            ),
        )
        verdict = self.engine.decide(switch_request)
        if verdict.decision not in _RELEASED_DECISIONS:
            return body, None, verdict.receipt_id
        switched = dict(body)
        switched["model"] = rule.switch_to
        return switched, rule.switch_to, verdict.receipt_id

    # -------------------------------------------------------------- upstream
    def _call_upstream(
        self,
        upstream: Upstream,
        body: dict[str, JsonValue],
        ingress: DecisionResponse,
        session: ProxySession,
    ) -> tuple[Optional[dict[str, JsonValue]], Optional[ProxyHttpResult]]:
        self._stamp(KV_LAST_REQUEST_AT)
        try:
            response_body = upstream(body)
        except Exception as exc:  # provider/network failure → evidence + 502
            self.engine.record(
                ingress.receipt_id,
                ExecutionOutcome(
                    status=ExecutionStatus.error,
                    notes="llm_proxy upstream error: {0}".format(exc),
                ),
            )
            return None, ProxyHttpResult(
                status=502,
                body=_error_body(
                    "[Zeus] upstream provider error: {0}".format(exc),
                    code="upstream_error",
                    receipt_id=ingress.receipt_id,
                ),
                receipt_id=ingress.receipt_id,
            )
        self._stamp(KV_LAST_RESPONSE_AT)
        return response_body if isinstance(response_body, dict) else {}, None

    # ----------------------------------------------------------- decision #2
    def _decide_tool_call(
        self, name: str, arguments_json: str, session: ProxySession
    ) -> tuple[DecisionResponse, str]:
        mapped = map_tool_call_for_host(session.host, name, arguments_json)
        request = DecisionRequest(
            principal_id=session.principal_id,
            session_id=session.session_id,
            run_id=session.resolved_run_id(),
            capability_id=mapped.capability_id,
            args=mapped.args,
            context=DecisionContext(
                host=session.host,
                surface=GateSurface.llm_proxy,
                objective_id=session.objective_id,
                defer_ask_to_owner=session.host in self._hook_owned_hosts,
            ),
        )
        response = self.engine.decide(request)
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id,
            host=session.host.value,
            surface=GateSurface.llm_proxy.value,
            capability_id=mapped.capability_id,
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        if response.decision in _RELEASED_DECISIONS:
            self._stamp_taint_for_release(mapped.capability_id, session)
        return response, mapped.capability_id

    def _govern_choices_tool_calls(
        self, response_body: dict[str, JsonValue], session: ProxySession
    ) -> tuple[dict[str, JsonValue], tuple[str, ...], int, int]:
        body = copy.deepcopy(response_body)
        receipts: list[str] = []
        blocked = 0
        released = 0
        choices = body.get("choices")
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                continue
            kept: list[JsonValue] = []
            notices: list[str] = []
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                function = function if isinstance(function, dict) else {}
                name = str(function.get("name", ""))
                arguments = str(function.get("arguments", "") or "")
                verdict, capability_id = self._decide_tool_call(name, arguments, session)
                receipts.append(verdict.receipt_id)
                if verdict.decision in _RELEASED_DECISIONS:
                    kept.append(tool_call)
                    released += 1
                else:
                    blocked += 1
                    notices.append(_block_notice(verdict, name, capability_id))
            if notices:
                existing = message.get("content")
                prefix = "{0}\n".format(existing) if isinstance(existing, str) and existing else ""
                message["content"] = prefix + "\n".join(notices)
            if kept:
                message["tool_calls"] = kept
            else:
                message.pop("tool_calls", None)
                if notices and choice.get("finish_reason") == "tool_calls":
                    choice["finish_reason"] = "stop"
        return body, tuple(receipts), blocked, released

    def _govern_output_items(
        self, response_body: dict[str, JsonValue], session: ProxySession
    ) -> tuple[dict[str, JsonValue], tuple[str, ...], int, int]:
        body = copy.deepcopy(response_body)
        receipts: list[str] = []
        blocked = 0
        released = 0
        output = body.get("output")
        if not isinstance(output, list):
            return body, (), 0, 0
        governed_output: list[JsonValue] = []
        for item in output:
            if not (isinstance(item, dict) and item.get("type") == "function_call"):
                governed_output.append(item)
                continue
            name = str(item.get("name", ""))
            arguments = str(item.get("arguments", "") or "")
            verdict, capability_id = self._decide_tool_call(name, arguments, session)
            receipts.append(verdict.receipt_id)
            if verdict.decision in _RELEASED_DECISIONS:
                governed_output.append(item)
                released += 1
                continue
            blocked += 1
            governed_output.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": _block_notice(verdict, name, capability_id),
                        }
                    ],
                }
            )
        body["output"] = governed_output
        return body, tuple(receipts), blocked, released

    # -------------------------------------------------------------- streaming
    def _stream_chunks(
        self,
        body: dict[str, JsonValue],
        session: ProxySession,
        ingress: DecisionResponse,
        redactor: Optional[RollingRedactor],
        first_chunk: Any,
        upstream_iter: Iterator[Any],
    ) -> Iterator[dict[str, JsonValue]]:
        buffers: dict[int, dict[int, _ToolCallEntry]] = {}
        released_by_choice: dict[int, int] = {}
        blocked_by_choice: dict[int, int] = {}
        meta: dict[str, JsonValue] = {}
        usage: Optional[dict[str, JsonValue]] = None
        hygiene_text: list[str] = []
        hygiene_size = 0
        # The upstream is already OPEN (the caller pulled first_chunk so connect
        # errors surfaced before headers). redactor: set for redact, None for
        # count and for the clean replay of a buffered block/ask response.
        upstream = upstream_iter if first_chunk is _STREAM_EXHAUSTED else chain([first_chunk], upstream_iter)
        first_seen = True
        stream_error: Optional[Exception] = None
        try:
            for chunk in upstream:
                if not isinstance(chunk, dict):
                    continue
                if first_seen:
                    self._stamp(KV_LAST_RESPONSE_AT)
                    first_seen = False
                for key in ("id", "model", "created", "object", "system_fingerprint"):
                    if key in chunk and key not in meta:
                        meta[key] = chunk[key]
                chunk_usage = chunk.get("usage")
                if isinstance(chunk_usage, dict):
                    usage = chunk_usage
                choices = chunk.get("choices")
                if not isinstance(choices, list) or not choices:
                    yield chunk
                    continue
                for out in self._stream_handle_choices(
                    chunk, choices, buffers, released_by_choice, blocked_by_choice,
                    meta, session, redactor,
                ):
                    if isinstance(out, str):  # hygiene accumulation marker (count mode)
                        if hygiene_size < _HYGIENE_SCAN_CAP:
                            hygiene_text.append(out)
                            hygiene_size += len(out)
                        continue
                    yield out
        except Exception as exc:  # D1: a mid-stream upstream failure must not look like a clean end
            stream_error = exc
        self._stamp(KV_LAST_RESPONSE_AT)
        if stream_error is not None:
            # tell the host the stream was cut short, and bind a FAILURE outcome
            # (a silent truncation would let the ledger overstate success).
            yield _content_chunk(
                meta, 0, "[Zeus] upstream stream aborted: {0}".format(stream_error)
            )
            self.engine.record(
                ingress.receipt_id,
                ExecutionOutcome(
                    status=ExecutionStatus.error,
                    notes="llm_proxy stream mid-abort: {0}".format(stream_error),
                ),
            )
            return
        if redactor is not None:
            if redactor.redactions:
                self._bump_findings(redactor.redactions)
                self._record_hygiene(
                    "allow", "hygiene_redacted:{0}".format(redactor.redactions), session
                )
        else:
            findings = _count_secret_findings("".join(hygiene_text))
            if findings:
                self._bump_findings(findings)
        actual = (
            self.meter.actual_units(str(body.get("model", "")), usage)
            if usage is not None
            else self.meter.estimate_request_units(body)
        )
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                cost_actual_units=actual,
                notes="llm_proxy chat.completions stream{0}".format(
                    "" if usage is not None else " (estimated)"
                ),
            ),
        )

    def _stream_buffered_hygiene(
        self,
        body: dict[str, JsonValue],
        session: ProxySession,
        upstream_stream: UpstreamStream,
        ingress: DecisionResponse,
        mode: HygieneMode,
    ) -> StreamOutcome:
        """block/ask over a stream: drain the whole upstream response first,
        then either replay it (clean) or withhold/park it (secret found). A
        stream emits incrementally, so the decision MUST precede any output."""
        self._stamp(KV_LAST_REQUEST_AT)
        chunks: list[dict[str, JsonValue]] = []
        buffered = 0
        overflow = False
        try:
            for chunk in upstream_stream(body):
                if not isinstance(chunk, dict):
                    continue
                buffered += len(json.dumps(chunk, ensure_ascii=False))
                if buffered > _STREAM_BUFFER_CAP:
                    overflow = True  # stop reading — never buffer without bound
                    break
                chunks.append(chunk)
        except Exception as exc:  # provider/network failure → evidence + 502
            self.engine.record(
                ingress.receipt_id,
                ExecutionOutcome(
                    status=ExecutionStatus.error,
                    notes="llm_proxy stream upstream error: {0}".format(exc),
                ),
            )
            return StreamOutcome(
                error=ProxyHttpResult(
                    status=502,
                    body=_error_body("[Zeus] upstream error", code="upstream_error"),
                    receipt_id=ingress.receipt_id,
                )
            )
        self._stamp(KV_LAST_RESPONSE_AT)
        if not chunks and not overflow:
            return StreamOutcome(error=self._stream_empty_error(ingress))
        if overflow:
            # a response too large to examine is withheld, not released unread
            # (same fail-closed doctrine as the tool_call buffer cap).
            self.engine.record(
                ingress.receipt_id,
                ExecutionOutcome(
                    status=ExecutionStatus.success,
                    cost_actual_units=self.meter.estimate_request_units(body),
                    notes="llm_proxy chat.completions stream (hygiene overflow)",
                ),
            )
            receipt_id = self._record_hygiene("deny", "hygiene_stream_overflow", session)
            return StreamOutcome(
                error=ProxyHttpResult(
                    status=403,
                    body=_error_body(
                        "[Zeus] response withheld: stream exceeded the {0}-char hygiene "
                        "buffer cap (hygiene={1})".format(_STREAM_BUFFER_CAP, mode.value),
                        code="hygiene_stream_overflow",
                        receipt_id=receipt_id,
                    ),
                    receipt_id=receipt_id,
                )
            )
        findings = _count_secret_findings(_assemble_stream_text(chunks)[:_HYGIENE_SCAN_CAP])
        if not findings:
            # clean → replay the already-drained chunks through the normal path
            # with NO redactor (count behavior); _stream_chunks records the cost.
            first = chunks[0] if chunks else _STREAM_EXHAUSTED
            rest: Iterator[Any] = iter(chunks[1:]) if chunks else iter(())
            return StreamOutcome(
                chunks=self._stream_chunks(body, session, ingress, None, first, rest)
            )
        # the upstream call cost money even though we withhold the body — record
        # the spend, then enforce the configured mode on the full response.
        usage = _stream_usage(chunks)
        actual = (
            self.meter.actual_units(str(body.get("model", "")), usage)
            if usage is not None
            else self.meter.estimate_request_units(body)
        )
        self.engine.record(
            ingress.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                cost_actual_units=actual,
                notes="llm_proxy chat.completions stream (hygiene {0})".format(mode.value),
            ),
        )
        self._bump_findings(findings)
        if mode is HygieneMode.block:
            receipt_id = self._record_hygiene("deny", "hygiene_block", session)
            return StreamOutcome(
                error=ProxyHttpResult(
                    status=403,
                    body=_error_body(
                        "[Zeus] response withheld: secret-shaped material detected (hygiene=block)",
                        code="hygiene_block",
                        receipt_id=receipt_id,
                    ),
                    receipt_id=receipt_id,
                    secret_findings=findings,
                )
            )
        receipt_id, parked_action_id = self._park_hygiene(session)
        return StreamOutcome(
            error=ProxyHttpResult(
                status=429,
                body=_error_body(
                    "[Zeus] response held for operator review (hygiene=ask); retry after approval",
                    code="hygiene_ask",
                    receipt_id=receipt_id,
                    parked_action_id=parked_action_id,
                ),
                receipt_id=receipt_id,
                secret_findings=findings,
            )
        )

    def _stream_handle_choices(
        self,
        chunk: dict[str, JsonValue],
        choices: list[JsonValue],
        buffers: dict[int, dict[int, _ToolCallEntry]],
        released_by_choice: dict[int, int],
        blocked_by_choice: dict[int, int],
        meta: dict[str, JsonValue],
        session: ProxySession,
        redactor: Optional[RollingRedactor] = None,
    ) -> Iterator[dict[str, JsonValue] | str]:
        pass_choices: list[JsonValue] = []
        synthesized: list[dict[str, JsonValue]] = []
        finish_chunks: list[JsonValue] = []
        for raw_choice in choices:
            if not isinstance(raw_choice, dict):
                continue
            choice_index = int(raw_choice.get("index", 0) or 0)
            delta = raw_choice.get("delta")
            delta = delta if isinstance(delta, dict) else {}
            finish_reason = raw_choice.get("finish_reason")
            tool_call_deltas = delta.get("tool_calls")
            if isinstance(tool_call_deltas, list):
                for item in tool_call_deltas:
                    if not isinstance(item, dict):
                        continue
                    synthesized.extend(
                        self._stream_absorb_tool_call_delta(
                            item, choice_index, buffers, released_by_choice,
                            blocked_by_choice, meta, session,
                        )
                    )
            clean_delta = {key: value for key, value in delta.items() if key != "tool_calls"}
            content = clean_delta.get("content")
            if isinstance(content, str) and content:
                if redactor is None:
                    yield content  # count-mode hygiene marker (accumulated by caller)
                else:
                    # rolling redaction: release the redacted prefix now, hold a
                    # trailing window so a secret split across deltas is caught.
                    release = redactor.feed(choice_index, content)
                    if release:
                        clean_delta["content"] = release
                    else:
                        clean_delta.pop("content", None)
            if finish_reason is not None:
                # release order: every buffered tool_call decision goes out
                # BEFORE the finish chunk — the host never sees a finish first.
                if redactor is not None:
                    tail = redactor.flush(choice_index)
                    if tail:
                        pass_choices.append(
                            {"index": choice_index, "delta": {"content": tail}, "finish_reason": None}
                        )
                synthesized.extend(
                    self._stream_finalize_choice(
                        choice_index, buffers, released_by_choice,
                        blocked_by_choice, meta, session,
                    )
                )
                adjusted = finish_reason
                if (
                    finish_reason == "tool_calls"
                    and released_by_choice.get(choice_index, 0) == 0
                    and blocked_by_choice.get(choice_index, 0) > 0
                ):
                    adjusted = "stop"
                finish_chunks.append(
                    {"index": choice_index, "delta": clean_delta, "finish_reason": adjusted}
                )
                continue
            if clean_delta:
                pass_choices.append(
                    {"index": choice_index, "delta": clean_delta, "finish_reason": None}
                )
        if pass_choices:
            passed = dict(chunk)
            passed["choices"] = pass_choices
            yield passed
        for synthetic in synthesized:
            yield synthetic
        if finish_chunks:
            final = dict(chunk)
            final["choices"] = finish_chunks
            yield final

    def _stream_absorb_tool_call_delta(
        self,
        item: dict[str, JsonValue],
        choice_index: int,
        buffers: dict[int, dict[int, _ToolCallEntry]],
        released_by_choice: dict[int, int],
        blocked_by_choice: dict[int, int],
        meta: dict[str, JsonValue],
        session: ProxySession,
    ) -> list[dict[str, JsonValue]]:
        buffer = buffers.setdefault(choice_index, {})
        tool_index = int(item.get("index", 0) or 0)
        # a delta for a HIGHER index means every lower-index call is complete
        ready = [
            index for index, entry in buffer.items() if index < tool_index and not entry.released
        ]
        out: list[dict[str, JsonValue]] = []
        for index in sorted(ready):
            out.extend(
                self._stream_release(
                    buffer[index], choice_index, index, released_by_choice,
                    blocked_by_choice, meta, session,
                )
            )
        entry = buffer.setdefault(tool_index, _ToolCallEntry())
        call_id = item.get("id")
        if isinstance(call_id, str) and call_id:
            entry.call_id = call_id
        function = item.get("function")
        function = function if isinstance(function, dict) else {}
        name = function.get("name")
        if isinstance(name, str) and name:
            entry.name += name
        arguments = function.get("arguments")
        if isinstance(arguments, str) and arguments:
            if len(entry.arguments) + len(arguments) > _TOOLCALL_BUFFER_CAP:
                entry.overflow = True
            else:
                entry.arguments += arguments
        return out

    def _stream_finalize_choice(
        self,
        choice_index: int,
        buffers: dict[int, dict[int, _ToolCallEntry]],
        released_by_choice: dict[int, int],
        blocked_by_choice: dict[int, int],
        meta: dict[str, JsonValue],
        session: ProxySession,
    ) -> list[dict[str, JsonValue]]:
        buffer = buffers.get(choice_index, {})
        out: list[dict[str, JsonValue]] = []
        for index in sorted(buffer):
            if not buffer[index].released:
                out.extend(
                    self._stream_release(
                        buffer[index], choice_index, index, released_by_choice,
                        blocked_by_choice, meta, session,
                    )
                )
        return out

    def _stream_release(
        self,
        entry: _ToolCallEntry,
        choice_index: int,
        tool_index: int,
        released_by_choice: dict[int, int],
        blocked_by_choice: dict[int, int],
        meta: dict[str, JsonValue],
        session: ProxySession,
    ) -> list[dict[str, JsonValue]]:
        entry.released = True
        if entry.overflow:
            # fail-closed, with its own audit record — never released unread
            event = self.engine.recorder.record_decision(
                run_id=session.resolved_run_id(),
                payload={
                    "principal_id": session.principal_id,
                    "session_id": session.session_id,
                    "capability_id": "llm.toolcall.{0}".format(entry.name or "unnamed"),
                    "host": session.host.value,
                    "surface": GateSurface.llm_proxy.value,
                    "decision": TrustDecision.DENY.value,
                    "reason": "toolcall_buffer_overflow",
                },
            )
            blocked_by_choice[choice_index] = blocked_by_choice.get(choice_index, 0) + 1
            notice = "[Zeus blocked: toolcall_buffer_overflow] tool call {0} exceeded the {1}-char argument cap (receipt {2})".format(
                entry.name or "unnamed", _TOOLCALL_BUFFER_CAP, event.record_id
            )
            return [_content_chunk(meta, choice_index, notice)]
        verdict, capability_id = self._decide_tool_call(entry.name, entry.arguments, session)
        if verdict.decision in _RELEASED_DECISIONS:
            released_by_choice[choice_index] = released_by_choice.get(choice_index, 0) + 1
            tool_call: dict[str, JsonValue] = {
                "index": tool_index,
                "id": entry.call_id or "call_zeus_{0}_{1}".format(choice_index, tool_index),
                "type": "function",
                "function": {"name": entry.name, "arguments": entry.arguments},
            }
            return [
                _envelope_chunk(
                    meta,
                    {"index": choice_index, "delta": {"tool_calls": [tool_call]}, "finish_reason": None},
                )
            ]
        blocked_by_choice[choice_index] = blocked_by_choice.get(choice_index, 0) + 1
        return [_content_chunk(meta, choice_index, _block_notice(verdict, entry.name, capability_id))]

    # -------------------------------------------------------------- internals
    def _stamp_taint_for_release(self, capability_id: str, session: ProxySession) -> None:
        record = self.engine.capabilities.get(capability_id)
        stamped = False
        if is_untrusted_source(capability_id, record):
            self.engine.taint.stamp(session.session_id, TaintLabel.untrusted, capability_id)
            stamped = True
        if is_private_source(capability_id):
            self.engine.taint.stamp(session.session_id, TaintLabel.private, capability_id)
            stamped = True
        if stamped and self._persist_taint is not None:
            self._persist_taint(self.engine.taint, (session.session_id,))

    def _hygiene_scan(self, body: dict[str, JsonValue]) -> int:
        findings = _count_secret_findings(json.dumps(body, ensure_ascii=False)[:_HYGIENE_SCAN_CAP])
        if findings:
            self._bump_findings(findings)
        return findings

    # --------------------------------------------------------- hygiene policy
    def _hygiene_apply(
        self, body: dict[str, JsonValue], session: ProxySession, *, kind: str
    ) -> tuple[dict[str, JsonValue], int, Optional[ProxyHttpResult]]:
        """Apply the configured hygiene mode to a non-streaming body. Returns
        (body, findings, refusal). A redaction/withholding is itself recorded
        as a decision receipt so the final action the host sees is evidenced."""
        mode = hygiene_mode_of(self.store)
        if mode is HygieneMode.count:
            return body, self._hygiene_scan(body), None
        if mode is HygieneMode.redact:
            redacted, count = (
                redact_chat_body(body) if kind == "chat" else redact_responses_body(body)
            )
            if count:
                self._bump_findings(count)
                receipt_id = self._record_hygiene("allow", "hygiene_redacted:{0}".format(count), session)
                zeus_meta: dict[str, JsonValue] = {"hygiene": "redacted", "receipt_id": receipt_id}
                redacted = {**redacted, "zeus": zeus_meta}
            return redacted, count, None
        # block | ask act only when there is something secret-shaped to act on
        findings = self._hygiene_scan(body)
        if not findings:
            return body, 0, None
        if mode is HygieneMode.block:
            receipt_id = self._record_hygiene("deny", "hygiene_block", session)
            return body, findings, ProxyHttpResult(
                status=403,
                body=_error_body(
                    "[Zeus] response withheld: secret-shaped material detected (hygiene=block)",
                    code="hygiene_block",
                    receipt_id=receipt_id,
                ),
                receipt_id=receipt_id,
                secret_findings=findings,
            )
        receipt_id, parked_action_id = self._park_hygiene(session)
        return body, findings, ProxyHttpResult(
            status=429,
            body=_error_body(
                "[Zeus] response held for operator review (hygiene=ask); "
                "retry after approval",
                code="hygiene_ask",
                receipt_id=receipt_id,
                parked_action_id=parked_action_id,
            ),
            receipt_id=receipt_id,
            secret_findings=findings,
        )

    def _record_hygiene(self, decision: str, reason: str, session: ProxySession) -> str:
        event = self.engine.recorder.record_decision(
            run_id=session.resolved_run_id(),
            payload={
                "principal_id": session.principal_id,
                "session_id": session.session_id,
                "capability_id": "llm.response.hygiene",
                "host": session.host.value,
                "surface": GateSurface.llm_proxy.value,
                "decision": decision,
                "reason": reason,
            },
        )
        return event.record_id

    def _park_hygiene(self, session: ProxySession) -> tuple[str, Optional[str]]:
        receipt_id = self._record_hygiene("ask", "hygiene_ask", session)
        action = TrustLoopAction(
            action_id="hygiene.{0}".format(receipt_id),
            run_id=session.resolved_run_id(),
            goal_contract_id=session.objective_id or "adhoc.objective",
            criterion_id="llm.response.hygiene",
            capability_id="llm.response.hygiene",
            budget=BudgetEnvelope(max_units=1, requested_units=0),
        )
        return receipt_id, self.engine.queue.park(action).parked_action_id

    def _bump_findings(self, count: int) -> None:
        if self.store is None:
            return
        current = self.store.kv_get(KV_SECRET_FINDINGS)
        total = int(current) if current is not None and current.isdigit() else 0
        self.store.kv_set(KV_SECRET_FINDINGS, str(total + count))

    def _stamp(self, key: str) -> None:
        if self.store is not None:
            self.store.kv_set(key, datetime.now(timezone.utc).isoformat())


def _block_notice(verdict: DecisionResponse, name: str, capability_id: str) -> str:
    if verdict.decision is TrustDecision.DENY:
        return "[Zeus blocked: {0}] tool call {1} ({2}) was removed; choose another approach.".format(
            verdict.reason, name or "unnamed", capability_id
        )
    return (
        "[Zeus] approval required for tool call {0} ({1}): {2} (parked: {3}). "
        "Operator resolves this outside the governed host; then re-issue the same call.".format(
            name or "unnamed", capability_id, verdict.reason, verdict.parked_action_id
        )
    )


def _content_chunk(
    meta: dict[str, JsonValue], choice_index: int, text: str
) -> dict[str, JsonValue]:
    return _envelope_chunk(
        meta, {"index": choice_index, "delta": {"content": text}, "finish_reason": None}
    )


def _envelope_chunk(
    meta: dict[str, JsonValue], choice: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    chunk: dict[str, JsonValue] = {
        "id": meta.get("id", "chatcmpl-zeus"),
        "object": "chat.completion.chunk",
        "created": meta.get("created", 0),
        "model": meta.get("model", ""),
        "choices": [choice],
    }
    return chunk


def _error_body(
    message: str,
    *,
    code: str,
    receipt_id: Optional[str] = None,
    parked_action_id: Optional[str] = None,
) -> dict[str, JsonValue]:
    zeus: dict[str, JsonValue] = {}
    if receipt_id is not None:
        zeus["receipt_id"] = receipt_id
    if parked_action_id is not None:
        zeus["parked_action_id"] = parked_action_id
    return {
        "error": {
            "message": message,
            "type": "zeus_governance",
            "code": code,
            "zeus": zeus,
        }
    }


def _usage_of(body: dict[str, JsonValue]) -> dict[str, JsonValue]:
    usage = body.get("usage")
    return usage if isinstance(usage, dict) else {}


def _count_secret_findings(text: str) -> int:
    """1 if the scanned body carries secret-shaped material, else 0. The scan
    only counts — the body returned to the host is never mutated; the ledger
    copies are redacted independently on append."""
    if not text:
        return 0
    return 1 if contains_secret_material(text) else 0


def _open_upstream(upstream_stream: UpstreamStream, body: dict[str, JsonValue]) -> tuple[Any, Iterator[Any]]:
    """Start the upstream stream and pull its first item NOW, so a connect/auth
    failure (e.g. 401) raises here — before SSE headers go out — instead of
    surfacing to the host as an empty 200 stream. Returns (first, iterator);
    first is _STREAM_EXHAUSTED when the stream opened but yielded nothing."""
    iterator = iter(upstream_stream(body))
    first = next(iterator, _STREAM_EXHAUSTED)
    return first, iterator


def _assemble_stream_text(chunks: list[dict[str, JsonValue]]) -> str:
    """Concatenate the assistant text deltas across buffered stream chunks —
    what block/ask hygiene scans before deciding whether to emit anything."""
    parts: list[str] = []
    for chunk in chunks:
        choices = chunk.get("choices")
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            content = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(content, str) and content:
                parts.append(content)
    return "".join(parts)


def _stream_usage(chunks: list[dict[str, JsonValue]]) -> Optional[dict[str, JsonValue]]:
    usage: Optional[dict[str, JsonValue]] = None
    for chunk in chunks:
        chunk_usage = chunk.get("usage")
        if isinstance(chunk_usage, dict):
            usage = chunk_usage
    return usage
