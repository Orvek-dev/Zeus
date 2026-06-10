from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import JsonValue, TypeAdapter

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustLoopAction,
)

_OPENAI_CAPABILITY_ID = "provider.external.generate"
_OPENAI_CREDENTIAL_SCOPE = "external.openai.readonly"
_OPENAI_NETWORK_HOST = "api.openai.com"
_EVIDENCE_TARGET = "mneme.v610.trust_loop"
_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


@dataclass(frozen=True)
class LiveChatReply:
    assistant_message: str
    trust_receipt_id: str | None = None
    trust_evidence_record_id: str | None = None
    broker_evidence_bound: bool = False
    handler_executed: bool = False


def openai_chat_reply_through_trust_loop(
    *,
    home: Path,
    message: str,
    model_id: str,
) -> LiveChatReply | None:
    if os.environ.get("ZEUS_ENABLE_OPENAI_LIVE_CHAT") != "1":
        return None
    api_key = os.environ.get("ZEUS_OPENAI_API_KEY") or os.environ.get("ZEUS_V110_PROVIDER_KEY")
    if api_key is None or api_key.strip() == "":
        return LiveChatReply(
            assistant_message="OpenAI live chat is enabled, but the OpenAI API key env var is missing.",
        )
    ledger = SQLiteEvidenceLedger(home / "trust" / "evidence.sqlite3")
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=_openai_graph(),
        handlers={
            _OPENAI_CAPABILITY_ID: lambda payload: _openai_http_chat(
                payload=payload,
                api_key=api_key,
            ),
        },
        ledger=ledger,
    )
    receipt = dispatcher.dispatch(
        _openai_action(message=message, model_id=model_id),
        lease=_openai_lease(),
        approval=_openai_approval(),
        approval_envelope=_openai_approval_envelope(),
    )
    if not receipt.handler_executed or receipt.result is None:
        return LiveChatReply(
            assistant_message="OpenAI live chat was blocked by Zeus Trust Loop: {0}.".format(
                receipt.blocked_reason or receipt.decision.value,
            ),
            trust_receipt_id=receipt.receipt_id,
            trust_evidence_record_id=receipt.evidence_record_id,
            broker_evidence_bound=receipt.broker_evidence_bound,
        )
    content = _result_text(receipt.result, "content")
    provider = _result_text(receipt.result, "provider")
    model = _result_text(receipt.result, "model_id")
    latency = _result_text(receipt.result, "latency_ms")
    return LiveChatReply(
        assistant_message="{0}\n\n[provider: {1}/{2}, latency_ms: {3}]".format(
            redact_secret_spans(content),
            provider,
            model,
            latency,
        ),
        trust_receipt_id=receipt.receipt_id,
        trust_evidence_record_id=receipt.evidence_record_id,
        broker_evidence_bound=receipt.broker_evidence_bound,
        handler_executed=receipt.handler_executed,
    )


def _openai_http_chat(
    *,
    payload: dict[str, JsonValue],
    api_key: str,
) -> dict[str, JsonValue]:
    message = _result_text(payload, "message")
    model_id = _result_text(payload, "model_id")
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": message}],
                "stream": False,
            },
        ).encode("utf-8"),
        headers={
            "Authorization": "Bearer {0}".format(api_key),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        return {"decision": "blocked", "reason": "provider_http_{0}".format(exc.code)}
    except (TimeoutError, URLError, OSError):
        return {"decision": "blocked", "reason": "provider_transport_error"}
    content = _openai_chat_content(body)
    if content is None:
        return {"decision": "blocked", "reason": "malformed_provider_response"}
    return {
        "provider": "openai",
        "model_id": model_id,
        "content": content,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def _openai_chat_content(body: str) -> str | None:
    try:
        payload = _JSON_OBJECT_ADAPTER.validate_json(body)
    except ValueError:
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        return None
    return content


def _openai_graph() -> CapabilityGraph:
    return CapabilityGraph(
        (
            CapabilityDescriptor(
                capability_id=_OPENAI_CAPABILITY_ID,
                name="provider_external_generate",
                risk=CapabilityRisk.high,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                side_effects=(SideEffect.network,),
            ),
        ),
    )


def _openai_action(*, message: str, model_id: str) -> TrustLoopAction:
    return TrustLoopAction(
        action_id="entry.chat.openai",
        run_id="entry.chat.openai.run",
        goal_contract_id="entry.chat.openai",
        criterion_id="REQ-ZEUS-TRUST-610:S1",
        capability_id=_OPENAI_CAPABILITY_ID,
        payload={"message": message, "model_id": model_id},
        risk=ActionRisk.high,
        reversibility=Reversibility.irreversible,
        budget=BudgetEnvelope(max_units=32, requested_units=1),
        evidence_target=_EVIDENCE_TARGET,
        credential_scope=_OPENAI_CREDENTIAL_SCOPE,
        network_host=_OPENAI_NETWORK_HOST,
        live_network=True,
    )


def _openai_lease() -> RuntimeLease:
    now = datetime.now(timezone.utc)
    return RuntimeLease(
        lease_id="entry.chat.openai.lease",
        objective_id="entry.chat.openai",
        principal_id="operator.local",
        run_id="entry.chat.openai.run",
        allowed_capabilities=(_OPENAI_CAPABILITY_ID,),
        credential_scopes=(_OPENAI_CREDENTIAL_SCOPE,),
        network_hosts=(_OPENAI_NETWORK_HOST,),
        budget_limit=32,
        evidence_target=_EVIDENCE_TARGET,
        live_transport_allowed=True,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
    )


def _openai_approval() -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="operator.local",
        run_id="entry.chat.openai.run",
        goal_contract_id="entry.chat.openai",
        approved_capabilities=[_OPENAI_CAPABILITY_ID],
        nonce="entry.chat.openai.local_opt_in",
    )


def _openai_approval_envelope() -> ApprovalEnvelope:
    return ApprovalEnvelope(
        envelope_id="entry.chat.openai.approval",
        capability_id=_OPENAI_CAPABILITY_ID,
        approval_receipt_id="entry.chat.openai.local_opt_in",
        predicted_effects=("send one chat completion request to OpenAI",),
        reversibility=Reversibility.irreversible,
        risk=ActionRisk.high,
        budget=BudgetEnvelope(max_units=32, requested_units=1),
    )


def _result_text(payload: dict[str, JsonValue], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return ""
