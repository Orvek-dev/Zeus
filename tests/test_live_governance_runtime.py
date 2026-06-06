from __future__ import annotations

import importlib
import json


def _future_runtime_api():
    module = importlib.import_module("zeus_agent.live_governance_runtime")
    return (
        module.GovernedLiveDispatcher,
        module.GovernedLiveRequest,
        module.LiveCapabilityRegistry,
        module.default_live_capability_registry,
        module.default_live_governance_trust_store,
    )


def test_provider_local_smoke_allows_only_with_full_governance_controls() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        live_capability_registry,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = _future_runtime_api()
    registry = default_live_capability_registry()
    dispatcher = governed_live_dispatcher(
        capability_registry=registry,
        trust_store=default_live_governance_trust_store(),
    )

    capability = registry.require("provider.local-smoke")
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert isinstance(registry, live_capability_registry)
    assert capability.lease_required is True
    assert capability.approval_required is True
    assert capability.promotion_guard_required is True
    assert capability.broker_evidence_required is True
    assert result.decision == "allowed"
    assert result.handler_executed is True
    assert result.lease_bound is True
    assert result.approval_bound is True
    assert result.promotion_guard_bound is True
    assert result.broker_evidence_bound is True
    assert result.no_secret_echo is True


def test_provider_local_smoke_public_refs_do_not_authorize_without_trusted_record() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        _default_live_governance_trust_store,
    ) = _future_runtime_api()
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("trusted_governance_record" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_unknown_capability_blocks_without_exception() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = _future_runtime_api()
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="attacker.cap",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("unknown_capability" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_missing_approval_blocks_without_handler_execution() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref=None,
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any(reason.endswith("missing_approval") for reason in result.blocked_reasons)
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_provider_local_smoke_raw_secret_credential_blocks_and_redacts() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    raw_secret = "".join(("sk", "-v210-live-governance-secret"))
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
        raw_credential=raw_secret,
    )

    result = dispatcher.dispatch(request)
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert result.decision == "blocked"
    assert any("raw_secret" in reason for reason in result.blocked_reasons)
    assert result.handler_executed is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.no_secret_echo is True
    assert raw_secret not in serialized


def test_provider_local_smoke_blocks_any_raw_credential_value() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
        raw_credential="plain-value",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert result.credential_material_accessed is False
    assert any("raw_credential" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_blocks_unleased_network_scope() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
        network_host="api.evil.example",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("network_scope" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_blocks_untrusted_credential_scope() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.production",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("credential_scope" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_blocks_bogus_governance_references() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="not-a-receipt",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("broker_evidence" in reason for reason in result.blocked_reasons)


def test_provider_local_smoke_blocks_bogus_promotion_guard_reference() -> None:
    (
        governed_live_dispatcher,
        governed_live_request,
        _,
        default_live_capability_registry,
        default_live_governance_trust_store,
    ) = (
        _future_runtime_api()
    )
    dispatcher = governed_live_dispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    request = governed_live_request(
        provider="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://attacker",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
    )

    result = dispatcher.dispatch(request)

    assert result.decision == "blocked"
    assert result.handler_executed is False
    assert any("promotion_guard" in reason for reason in result.blocked_reasons)
