from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Final, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
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
from zeus_agent.execution_integrity_runtime import assert_claim, claim_from_provider_receipt
from zeus_agent.safe_http_runtime import url_violation
from zeus_agent.security.credentials import contains_secret_material, redact_secret_spans
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    DecisionReceipt,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustLoopAction,
)

from .models import ProviderReceipt, ProviderRequest, ProviderVendor

_EXTERNAL_VENDORS: Final = frozenset({ProviderVendor.openai, ProviderVendor.anthropic})
_CAPABILITY_BY_VENDOR: Final[dict[ProviderVendor, str]] = {
    ProviderVendor.fake: "provider.fake.generate",
    ProviderVendor.local: "provider.local.generate",
    ProviderVendor.openai: "provider.openai.generate",
    ProviderVendor.anthropic: "provider.anthropic.generate",
}
_EVIDENCE_TARGET: Final = "mneme.provider_capability"
_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])

SecretResolver = Callable[[str], Optional[str]]
VendorHandler = Callable[[dict[str, JsonValue]], dict[str, JsonValue]]


class CanonicalProviderHandler:
    """The single provider entry point. Fake, local, and external vendors all
    dispatch through one ``GovernedExecutionDispatcher`` — never directly — so a
    provider call cannot happen without broker evidence, lease, and approval.

    Fail-closed boundaries enforced before any dispatch:
      - external vendor without an ``env://`` secret_ref, or a raw key → blocked
      - model not in a non-empty allowlist → blocked
      - endpoint host not in a non-empty allowlist, or non-https scheme → blocked
      - empty message or raw secret material in the message → blocked
    """

    def __init__(self, *, ledger: SQLiteEvidenceLedger, secret_resolver: Optional[SecretResolver] = None) -> None:
        self._ledger = ledger
        self._resolve = secret_resolver if secret_resolver is not None else _env_secret

    def generate(
        self,
        request: ProviderRequest,
        *,
        lease: Optional[RuntimeLease] = None,
        approval: Optional[ApprovalReceipt] = None,
        approval_envelope: Optional[ApprovalEnvelope] = None,
    ) -> ProviderReceipt:
        external = request.vendor in _EXTERNAL_VENDORS
        block = self._guard(request)
        if block is not None:
            return _blocked(request, block)

        # External live calls must carry an explicit, caller-provided lease,
        # approval, and envelope. Only fake/local may fall back to defaults.
        if external and (lease is None or approval is None or approval_envelope is None):
            return _blocked(request, "external_requires_explicit_authorization")

        secret: Optional[str] = None
        if external:
            secret = self._resolve(_env_var(request.secret_ref))
            if secret is None or secret.strip() == "":
                return _blocked(request, "secret_ref_unresolved")

        capability_id = _CAPABILITY_BY_VENDOR[request.vendor]
        dispatcher = GovernedExecutionDispatcher(
            capability_graph=_graph(capability_id, request.vendor),
            handlers={capability_id: _vendor_handler(request, secret)},
            ledger=self._ledger,
        )
        run_id = "provider.{0}.run".format(request.vendor.value)
        receipt = dispatcher.dispatch(
            _action(request, capability_id),
            lease=lease if lease is not None else _default_lease(request, capability_id),
            approval=approval if approval is not None else _default_approval(capability_id, run_id),
            approval_envelope=approval_envelope
            if approval_envelope is not None
            else _default_envelope(request, capability_id),
        )
        provider_receipt = _receipt_from(receipt, request)
        # Active execution-integrity gate (M0-5): a returned receipt that claims
        # execution must carry broker evidence, or this surface refuses it.
        assert_claim(claim_from_provider_receipt(provider_receipt))
        return provider_receipt

    def _guard(self, request: ProviderRequest) -> Optional[str]:
        if contains_secret_material(request.message):
            return "raw_secret_in_message"
        if request.vendor in _EXTERNAL_VENDORS:
            return _external_guard(request)
        if request.vendor is ProviderVendor.local:
            return _local_guard(request)
        # fake: an optional allowlist still applies if the caller set one.
        if request.allowed_models and request.model_id not in request.allowed_models:
            return "model_not_allowlisted"
        return None


def _external_guard(request: ProviderRequest) -> Optional[str]:
    # Empty allowlists are a BLOCK for live external providers, never allow-all.
    if not request.allowed_models:
        return "external_model_allowlist_required"
    if request.model_id not in request.allowed_models:
        return "model_not_allowlisted"
    if request.secret_ref is None or not request.secret_ref.startswith("env://"):
        return "raw_secret_ref_not_allowed"
    if request.endpoint is None:
        return "endpoint_required"
    parsed = urlparse(request.endpoint)
    if parsed.scheme != "https":
        return "endpoint_scheme_not_https"
    if not request.allowed_hosts:
        return "external_host_allowlist_required"
    if parsed.hostname not in request.allowed_hosts:
        return "endpoint_not_allowlisted"
    # Defense in depth: even an allowlisted host must not be an internal/metadata
    # target (catches a misconfigured allowlist like "10.0.0.5").
    ssrf = url_violation(request.endpoint, allowed_hosts=request.allowed_hosts)
    if ssrf is not None:
        return "ssrf_blocked:{0}".format(ssrf)
    return None


def _local_guard(request: ProviderRequest) -> Optional[str]:
    if request.allowed_models and request.model_id not in request.allowed_models:
        return "model_not_allowlisted"
    endpoint = request.endpoint or "http://127.0.0.1/v1/chat/completions"
    if urlparse(endpoint).hostname not in {"127.0.0.1", "localhost", "::1"}:
        return "local_endpoint_not_loopback"
    return None


def _vendor_handler(request: ProviderRequest, secret: Optional[str]) -> VendorHandler:
    if request.vendor is ProviderVendor.fake:
        return _fake_handler
    if request.vendor is ProviderVendor.local:
        return _local_handler(request)
    return _external_handler(request, secret or "")


def _fake_handler(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    message = _text(payload, "message")
    model_id = _text(payload, "model_id")
    return {
        "provider": "fake",
        "model_id": model_id,
        "content": "[fake:{0}] {1}".format(model_id, redact_secret_spans(message)),
        "latency_ms": 0,
    }


def _local_handler(request: ProviderRequest) -> VendorHandler:
    # Loopback is enforced pre-dispatch in _local_guard, so the handler only runs
    # the (already-validated) local call.
    endpoint = request.endpoint or "http://127.0.0.1/v1/chat/completions"

    def handler(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _http_chat(
            endpoint=endpoint,
            headers={"Content-Type": "application/json"},
            body=_openai_style_body(payload),
            timeout_ms=request.timeout_ms,
            parse=_parse_openai_content,
            provider="local",
        )

    return handler


def _external_handler(request: ProviderRequest, secret: str) -> VendorHandler:
    def handler(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if request.vendor is ProviderVendor.anthropic:
            return _http_chat(
                endpoint=request.endpoint or "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": secret,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                body=_anthropic_body(payload),
                timeout_ms=request.timeout_ms,
                parse=_parse_anthropic_content,
                provider="anthropic",
            )
        return _http_chat(
            endpoint=request.endpoint or "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer {0}".format(secret), "Content-Type": "application/json"},
            body=_openai_style_body(payload),
            timeout_ms=request.timeout_ms,
            parse=_parse_openai_content,
            provider="openai",
        )

    return handler


def _http_chat(
    *,
    endpoint: str,
    headers: dict[str, str],
    body: dict[str, JsonValue],
    timeout_ms: int,
    parse: Callable[[str], Optional[str]],
    provider: str,
) -> dict[str, JsonValue]:
    request = Request(endpoint, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    started = time.monotonic()
    # Post-network failures are NOT "decision: blocked": the call was attempted,
    # so the handler DID execute (a side effect occurred). Returning an
    # executed-with-error result keeps handler_executed=True in the receipt and
    # the audit trail honest. "decision: blocked" is reserved for pre-execution
    # refusals where no side effect happened.
    try:
        with urlopen(request, timeout=timeout_ms / 1000) as response:  # scheme guarded upstream
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        return {"provider": provider, "error": "provider_http_{0}".format(exc.code)}
    except (TimeoutError, URLError, OSError):
        return {"provider": provider, "error": "provider_transport_error"}
    content = parse(raw)
    if content is None:
        return {"provider": provider, "error": "malformed_provider_response"}
    return {
        "provider": provider,
        "content": content,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def _openai_style_body(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "model": _text(payload, "model_id"),
        "messages": [{"role": "user", "content": _text(payload, "message")}],
        "stream": False,
    }


def _anthropic_body(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "model": _text(payload, "model_id"),
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": _text(payload, "message")}],
    }


def _parse_openai_content(body: str) -> Optional[str]:
    payload = _safe_json(body)
    if payload is None:
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) and content.strip() != "" else None


def _parse_anthropic_content(body: str) -> Optional[str]:
    payload = _safe_json(body)
    if payload is None:
        return None
    content = payload.get("content")
    if not isinstance(content, list) or not content or not isinstance(content[0], dict):
        return None
    text = content[0].get("text")
    return text if isinstance(text, str) and text.strip() != "" else None


def _safe_json(body: str) -> Optional[dict[str, JsonValue]]:
    try:
        return _JSON_OBJECT_ADAPTER.validate_json(body)
    except ValueError:
        return None


def _graph(capability_id: str, vendor: ProviderVendor) -> CapabilityGraph:
    risk = CapabilityRisk.high if vendor in _EXTERNAL_VENDORS else CapabilityRisk.low
    side_effects = (SideEffect.network,) if vendor in _EXTERNAL_VENDORS or vendor is ProviderVendor.local else ()
    return CapabilityGraph(
        (
            CapabilityDescriptor(
                capability_id=capability_id,
                name=capability_id.replace(".", "_"),
                risk=risk,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                side_effects=list(side_effects),
            ),
        ),
    )


def _action(request: ProviderRequest, capability_id: str) -> TrustLoopAction:
    external = request.vendor in _EXTERNAL_VENDORS
    return TrustLoopAction(
        action_id="provider.{0}".format(request.vendor.value),
        run_id="provider.{0}.run".format(request.vendor.value),
        goal_contract_id="provider.{0}".format(request.vendor.value),
        criterion_id="REQ-ZEUS-PROVIDER:S1",
        capability_id=capability_id,
        payload={"message": request.message, "model_id": request.model_id},
        risk=ActionRisk.high if external else ActionRisk.low,
        reversibility=Reversibility.irreversible if external else Reversibility.reversible,
        budget=BudgetEnvelope(max_units=request.budget_max_units, requested_units=request.budget_requested_units),
        evidence_target=_EVIDENCE_TARGET,
        credential_scope=_credential_scope(request) if external else None,
        network_host=_host(request) if external else None,
        live_network=external,
    )


def _default_lease(request: ProviderRequest, capability_id: str) -> RuntimeLease:
    now = datetime.now(timezone.utc)
    external = request.vendor in _EXTERNAL_VENDORS
    return RuntimeLease(
        lease_id="provider.{0}.lease".format(request.vendor.value),
        objective_id="provider.{0}".format(request.vendor.value),
        principal_id="operator.local",
        run_id="provider.{0}.run".format(request.vendor.value),
        allowed_capabilities=(capability_id,),
        credential_scopes=(_credential_scope(request),) if external else (),
        network_hosts=(_host(request),) if external else (),
        budget_limit=request.budget_max_units,
        evidence_target=_EVIDENCE_TARGET,
        live_transport_allowed=external,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
    )


def _default_approval(capability_id: str, run_id: str) -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="operator.local",
        run_id=run_id,
        goal_contract_id="provider.{0}".format(capability_id.split(".")[1]),
        approved_capabilities=[capability_id],
        nonce="{0}.local_opt_in".format(capability_id),
    )


def _default_envelope(request: ProviderRequest, capability_id: str) -> ApprovalEnvelope:
    external = request.vendor in _EXTERNAL_VENDORS
    return ApprovalEnvelope(
        envelope_id="{0}.approval".format(capability_id),
        capability_id=capability_id,
        approval_receipt_id="{0}.local_opt_in".format(capability_id),
        predicted_effects=("send one generation request to {0}".format(request.vendor.value),),
        reversibility=Reversibility.irreversible if external else Reversibility.reversible,
        risk=ActionRisk.high if external else ActionRisk.low,
        budget=BudgetEnvelope(max_units=request.budget_max_units, requested_units=request.budget_requested_units),
    )


def _receipt_from(receipt: DecisionReceipt, request: ProviderRequest) -> ProviderReceipt:
    content = None
    provider_error = None
    if receipt.result is not None:
        raw = receipt.result.get("content")
        if isinstance(raw, str):
            content = redact_secret_spans(raw)
        err = receipt.result.get("error")
        if isinstance(err, str):
            provider_error = err
    return ProviderReceipt(
        decision=receipt.decision.value,
        vendor=request.vendor,
        model_id=request.model_id,
        handler_executed=receipt.handler_executed,
        content=content,
        blocked_reason=receipt.blocked_reason,
        provider_error=provider_error,
        evidence_record_id=receipt.evidence_record_id,
        broker_evidence_bound=receipt.broker_evidence_bound,
        no_secret_echo=receipt.no_secret_echo,
    )


def _blocked(request: ProviderRequest, reason: str) -> ProviderReceipt:
    return ProviderReceipt(
        decision="blocked",
        vendor=request.vendor,
        model_id=request.model_id,
        handler_executed=False,
        blocked_reason=reason,
        no_secret_echo=not contains_secret_material(reason),
    )


def _credential_scope(request: ProviderRequest) -> str:
    return "external.{0}.readonly".format(request.vendor.value)


def _host(request: ProviderRequest) -> str:
    if request.endpoint is None:
        return "api.{0}.com".format(request.vendor.value)
    return urlparse(request.endpoint).hostname or "api.{0}.com".format(request.vendor.value)


def _env_var(secret_ref: Optional[str]) -> str:
    if secret_ref is None:
        return ""
    return secret_ref[len("env://"):] if secret_ref.startswith("env://") else secret_ref


def _env_secret(var: str) -> Optional[str]:
    if var == "":
        return None
    return os.environ.get(var)


def _text(payload: dict[str, JsonValue], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""
