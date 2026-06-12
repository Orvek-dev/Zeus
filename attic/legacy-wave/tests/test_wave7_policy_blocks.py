from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.runtime_promotion import LiveTransportPromotionRequest, RollbackPlan
from zeus_agent.transport_runtime import (
    AuthorityRequirement,
    SandboxProbeDefinition,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
    TransportPolicyBlock,
    TransportRegistry,
    TransportRegistryError,
    default_wave7_manifests,
)
from zeus_agent.wave7_scenarios import wave7_policy_blocks_payload
from zeus_agent.workflow_runtime.jobs import RetryPolicy


def test_wave7_policy_blocks_malformed_duplicate_secret_and_live_enablement() -> None:
    # Given: adversarial Wave7 policy inputs.
    raw_secret = "ghp_TEST_FIXTURE"

    # When: the policy-block scenario runs.
    payload = wave7_policy_blocks_payload(raw_secret=raw_secret)

    # Then: each unsafe path is blocked before handler or network execution.
    assert payload["malformed_manifest"] == "blocked"
    assert payload["duplicate_transport_id"] == "blocked"
    assert payload["secret_like_credential_scope"] == "redacted"
    assert payload["unhealthy_probe"] == "blocked"
    assert payload["live_enablement_without_promotion"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_transport_registry_rejects_duplicate_transport_id_without_replacement() -> None:
    # Given: an existing manifest is already registered.
    registry = TransportRegistry()
    first = default_wave7_manifests()[0]
    registry.register(first)
    duplicate = first.model_copy(update={"display_name": "Replacement"})

    # When: the same transport id is registered again.
    with pytest.raises(TransportRegistryError) as raised:
        registry.register(duplicate)

    # Then: the duplicate is blocked and the original remains registered.
    assert raised.value.reason == "duplicate_transport_id"
    assert registry.manifest_report()[0]["display_name"] == first.display_name


def test_transport_manifest_rejects_secret_like_credential_scope_without_echo() -> None:
    # Given: raw credential material is mistakenly supplied as a scope label.
    raw_secret = "sk-wave7-secret"

    # When: the manifest boundary parses the input.
    with pytest.raises(ValidationError) as raised:
        TransportAdapterManifest(
            transport_id="api.secret",
            kind=TransportKind.api,
            display_name="Secret API",
            capability_id="api.secret.fetch",
            policy=TransportPolicy(
                policy_labels=("external-api",),
                authority_requirements=(
                    AuthorityRequirement(
                        capability_id="api.secret.fetch",
                        credential_scope=raw_secret,
                    ),
                ),
                credential_scope_label=raw_secret,
            ),
        )

    # Then: the parser blocks the unsafe value without exposing it downstream.
    assert "secret_like_credential_scope" in str(raised.value)
    assert raw_secret not in str(raised.value)


def test_transport_policy_rejects_live_transport_true_at_boundary() -> None:
    # Given: a manifest policy attempts to mark a future transport as live.
    with pytest.raises(ValidationError) as raised:
        TransportPolicy(
            policy_labels=("external-ai",),
            authority_requirements=(
                AuthorityRequirement(capability_id="provider.external.generate"),
            ),
            live_transport=True,
        )

    # Then: Wave7 blocks the live flag at parse time.
    assert "live_transport_not_authorized" in str(raised.value)


def test_transport_registry_rejects_live_transport_copy_before_probe_or_approval() -> None:
    # Given: a caller bypasses policy validation by copying a live flag onto a manifest.
    registry = TransportRegistry()
    manifest = default_wave7_manifests()[0]
    live_policy = manifest.policy.model_copy(update={"live_transport": True})
    live_manifest = manifest.model_copy(update={"policy": live_policy})

    # When: the tampered manifest is registered.
    with pytest.raises(TransportRegistryError) as raised:
        registry.register(live_manifest)

    # Then: the registry blocks it before any probe, approval, handler, or network path.
    assert raised.value.reason == "live_transport_not_authorized"
    assert registry.manifest_report() == []


def test_transport_policy_block_redacts_input_before_serialization() -> None:
    # Given: a policy block is constructed with accidental raw secret material.
    raw_secret = "sk-wave7-secret"

    # When: the block is serialized for evidence or CLI output.
    block = TransportPolicyBlock(
        reason="secret_like_credential_scope",
        redacted_input=raw_secret,
    )
    serialized = json.dumps(block.model_dump(mode="json"), sort_keys=True)

    # Then: the raw secret never leaves the boundary.
    assert block.redacted_input == "sk-...redacted"
    assert raw_secret not in serialized


def test_transport_policy_block_redacts_model_copy_secret_at_serialization_boundary() -> None:
    # Given: model_copy bypasses validators and injects raw secret material.
    raw_secret = "sk-wave7-secret"
    block = TransportPolicyBlock(
        reason="secret_like_credential_scope",
        redacted_input="sk-...redacted",
    )
    tampered = block.model_copy(update={"redacted_input": raw_secret})

    # When: the block is serialized.
    payload = tampered.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)

    # Then: serializer-level redaction still prevents raw secret output.
    assert tampered.redacted_input == "sk-...redacted"
    assert payload["redacted_input"] == "sk-...redacted"
    assert raw_secret not in repr(tampered)
    assert raw_secret not in json.dumps(dict(tampered), sort_keys=True)
    assert raw_secret not in serialized


def test_live_enablement_requires_healthy_probe_and_promotion_authority() -> None:
    # Given: a registered provider transport with an unhealthy probe state.
    registry = TransportRegistry()
    manifest = default_wave7_manifests()[0]
    registry.register(manifest)
    registry.run_probe(
        SandboxProbeDefinition(
            probe_id="probe-provider-unhealthy",
            transport_id=manifest.transport_id,
            expected_health=TransportHealth.unhealthy,
        )
    )
    request = LiveTransportPromotionRequest(
        promotion_id="promotion-wave7-provider",
        capability_id=manifest.capability_id,
        transport_kind="provider",
        idempotency_key="idem-wave7-provider",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(
            command="disable-live-transport",
            target=manifest.capability_id,
        ),
    )
    authority = AuthorityContext(
        principal_id="wave7-principal",
        run_id="wave7-run",
        goal_contract_id="wave7-goal",
        capability_grants=[CapabilityGrant(capability_id=manifest.capability_id)],
    )

    # When: live enablement is requested.
    result = registry.evaluate_live_enablement(request, authority=authority)

    # Then: unhealthy health blocks before Wave6 promotion can authorize anything.
    assert result.reason == "unhealthy_probe"
    assert result.handler_executed is False
    assert result.network_opened is False


def test_live_enablement_blocks_transport_kind_mismatch_before_promotion() -> None:
    # Given: a healthy provider manifest is registered.
    registry = TransportRegistry()
    manifest = default_wave7_manifests()[0]
    registry.register(manifest)
    registry.run_probe(
        SandboxProbeDefinition(
            probe_id="probe-provider-healthy",
            transport_id=manifest.transport_id,
            expected_health=TransportHealth.healthy,
        )
    )
    request = LiveTransportPromotionRequest(
        promotion_id="promotion-wave7-kind-mismatch",
        capability_id=manifest.capability_id,
        transport_kind="api",
        idempotency_key="idem-wave7-kind-mismatch",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(
            command="disable-live-transport",
            target=manifest.capability_id,
        ),
    )

    # When: live enablement uses the wrong transport kind for that capability.
    result = registry.evaluate_live_enablement(
        request,
        authority=AuthorityContext(
            principal_id="wave7-principal",
            run_id="wave7-run",
            goal_contract_id="wave7-goal",
            capability_grants=[CapabilityGrant(capability_id=manifest.capability_id)],
        ),
    )

    # Then: registry policy blocks before Wave6 promotion authorization.
    assert result.reason == "transport_kind_mismatch"
    assert result.handler_executed is False
    assert result.network_opened is False
