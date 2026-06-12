from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.provider_capability_runtime import (
    CanonicalProviderHandler,
    ProviderRequest,
    ProviderVendor,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    Reversibility,
    SQLiteEvidenceLedger,
)


def _external_auth(capability_id: str, host: str):
    now = datetime.now(timezone.utc)
    lease = RuntimeLease(
        lease_id="ext.lease",
        objective_id="ext.obj",
        principal_id="operator.local",
        run_id="provider.openai.run",
        allowed_capabilities=(capability_id,),
        credential_scopes=("external.openai.readonly",),
        network_hosts=(host,),
        budget_limit=32,
        evidence_target="mneme.provider_capability",
        live_transport_allowed=True,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
    )
    approval = ApprovalReceipt(
        principal_id="operator.local",
        run_id="provider.openai.run",
        goal_contract_id="provider.openai",
        approved_capabilities=[capability_id],
        nonce="ext.opt_in",
    )
    envelope = ApprovalEnvelope(
        envelope_id="ext.env",
        capability_id=capability_id,
        approval_receipt_id="ext.opt_in",
        predicted_effects=("send one generation request",),
        reversibility=Reversibility.irreversible,
        risk=ActionRisk.high,
        budget=BudgetEnvelope(max_units=32, requested_units=1),
    )
    return lease, approval, envelope


def _handler(tmp_path, secret_resolver=None) -> CanonicalProviderHandler:
    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    return CanonicalProviderHandler(ledger=ledger, secret_resolver=secret_resolver)


# --- The happy path: fake vendor flows through the dispatcher --------------


def test_fake_vendor_executes_through_dispatcher(tmp_path) -> None:
    handler = _handler(tmp_path)
    receipt = handler.generate(
        ProviderRequest(vendor=ProviderVendor.fake, model_id="fake.model", message="hello zeus")
    )
    assert receipt.handler_executed is True
    assert receipt.broker_evidence_bound is True
    # The only way content exists is via a real dispatch that bound broker evidence.
    assert receipt.content is not None and "hello zeus" in receipt.content
    assert receipt.evidence_record_id is not None
    assert receipt.no_secret_echo is True


def test_every_call_records_evidence(tmp_path) -> None:
    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    handler = CanonicalProviderHandler(ledger=ledger)
    handler.generate(ProviderRequest(vendor=ProviderVendor.fake, model_id="m", message="hi"))
    # A provider call cannot happen without leaving a verifiable evidence record.
    assert len(ledger.records()) == 1
    assert ledger.verify_chain().ok is True


# --- Fail-closed boundaries (no network needed) ----------------------------


def _openai_request(**overrides: object) -> ProviderRequest:
    base: dict[str, object] = {
        "vendor": ProviderVendor.openai,
        "model_id": "gpt-x",
        "message": "hi",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "secret_ref": "env://OPENAI_KEY",
        "allowed_models": ("gpt-x",),
        "allowed_hosts": ("api.openai.com",),
    }
    base.update(overrides)
    return ProviderRequest(**base)  # type: ignore[arg-type]


def test_external_empty_model_allowlist_is_blocked(tmp_path) -> None:
    # P1: an empty allowlist must BLOCK a live external provider, never allow-all.
    handler = _handler(tmp_path, secret_resolver=lambda _var: "resolved")
    lease, approval, envelope = _external_auth("provider.openai.generate", "api.openai.com")
    receipt = handler.generate(
        _openai_request(allowed_models=()),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "external_model_allowlist_required"
    assert receipt.handler_executed is False


def test_external_empty_host_allowlist_is_blocked(tmp_path) -> None:
    handler = _handler(tmp_path, secret_resolver=lambda _var: "resolved")
    lease, approval, envelope = _external_auth("provider.openai.generate", "api.openai.com")
    receipt = handler.generate(
        _openai_request(allowed_hosts=()),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "external_host_allowlist_required"


def test_external_without_explicit_authorization_is_blocked(tmp_path) -> None:
    # P1: external live calls require a caller-provided lease + approval + envelope.
    handler = _handler(tmp_path, secret_resolver=lambda _var: "resolved")
    receipt = handler.generate(_openai_request())  # no lease/approval passed
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "external_requires_explicit_authorization"
    assert receipt.handler_executed is False


def test_raw_key_secret_ref_is_rejected_before_dispatch(tmp_path) -> None:
    handler = _handler(tmp_path)
    lease, approval, envelope = _external_auth("provider.openai.generate", "api.openai.com")
    receipt = handler.generate(
        _openai_request(secret_ref="sk-RAWKEY"),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "raw_secret_ref_not_allowed"
    assert receipt.handler_executed is False


def test_external_vendor_without_resolvable_secret_is_blocked(tmp_path) -> None:
    handler = _handler(tmp_path, secret_resolver=lambda _var: None)
    lease, approval, envelope = _external_auth("provider.anthropic.generate", "api.anthropic.com")
    receipt = handler.generate(
        ProviderRequest(
            vendor=ProviderVendor.anthropic,
            model_id="claude-x",
            message="hi",
            endpoint="https://api.anthropic.com/v1/messages",
            secret_ref="env://MISSING_KEY",
            allowed_models=("claude-x",),
            allowed_hosts=("api.anthropic.com",),
        ),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "secret_ref_unresolved"


def test_non_allowlisted_model_is_blocked(tmp_path) -> None:
    handler = _handler(tmp_path)
    receipt = handler.generate(
        ProviderRequest(
            vendor=ProviderVendor.fake,
            model_id="rogue.model",
            message="hi",
            allowed_models=("fake.model",),
        )
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "model_not_allowlisted"


def test_non_https_endpoint_is_blocked(tmp_path) -> None:
    handler = _handler(tmp_path, secret_resolver=lambda _var: "resolved")
    lease, approval, envelope = _external_auth("provider.openai.generate", "api.openai.com")
    receipt = handler.generate(
        _openai_request(endpoint="http://api.openai.com/v1/chat/completions"),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "endpoint_scheme_not_https"


def test_non_allowlisted_endpoint_host_is_blocked(tmp_path) -> None:
    handler = _handler(tmp_path, secret_resolver=lambda _var: "resolved")
    lease, approval, envelope = _external_auth("provider.openai.generate", "api.openai.com")
    receipt = handler.generate(
        _openai_request(endpoint="https://evil.example.com/v1/chat/completions"),
        lease=lease, approval=approval, approval_envelope=envelope,
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "endpoint_not_allowlisted"


def test_local_transport_failure_records_handler_executed(tmp_path) -> None:
    # P1: a network attempt that fails is "executed with error", NOT "blocked".
    # The audit must show the side effect happened (handler_executed=True), with
    # the failure surfaced as provider_error, not as a pre-execution block.
    handler = _handler(tmp_path)
    receipt = handler.generate(
        ProviderRequest(
            vendor=ProviderVendor.local,
            model_id="local.model",
            message="hi",
            endpoint="http://127.0.0.1:9/v1/chat/completions",  # closed loopback port
            timeout_ms=500,
        )
    )
    assert receipt.handler_executed is True
    assert receipt.broker_evidence_bound is True
    assert receipt.content is None
    assert receipt.provider_error == "provider_transport_error"
    assert receipt.blocked_reason is None


def test_raw_secret_in_message_is_blocked_and_not_echoed(tmp_path) -> None:
    handler = _handler(tmp_path)
    receipt = handler.generate(
        ProviderRequest(
            vendor=ProviderVendor.fake,
            model_id="fake.model",
            message="my key is sk-proj-THISISSECRET ok",
        )
    )
    assert receipt.decision == "blocked"
    assert receipt.blocked_reason == "raw_secret_in_message"
    assert "THISISSECRET" not in str(receipt.to_payload())
