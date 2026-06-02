from __future__ import annotations

import json

from pydantic import ValidationError

from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.runtime_promotion import LiveTransportPromotionRequest, RollbackPlan
from zeus_agent.security.credentials import redact_secret_like
from zeus_agent.transport_runtime import (
    AuthorityRequirement,
    SandboxProbeDefinition,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
    TransportRegistry,
    TransportRegistryError,
    default_wave7_manifests,
    default_wave7_probes,
)
from zeus_agent.workflow_runtime.jobs import RetryPolicy


def wave7_transport_registry_payload() -> dict[str, object]:
    registry = _probed_registry()
    summary = registry.summary()
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "manifests": registry.manifest_report(),
        "health": registry.health_report(),
        "probe_receipts": registry.probe_report(),
        "sandbox_probe_count": summary.sandbox_probe_count,
        "live_transport": summary.live_transport,
    }
    return {**payload, "no_secret_echo": _no_secret_echo(payload)}


def wave7_policy_blocks_payload(*, raw_secret: str) -> dict[str, object]:
    duplicate = _duplicate_block()
    secret = _secret_block(raw_secret)
    unhealthy = _unhealthy_enablement_block()
    live = _live_enablement_block()
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "malformed_manifest": _malformed_block(),
        "duplicate_transport_id": duplicate,
        "secret_like_credential_scope": secret,
        "secret_redaction": redact_secret_like(raw_secret),
        "unhealthy_probe": unhealthy,
        "live_enablement_without_promotion": live,
        "handler_executed": False,
        "network_opened": False,
    }
    return {**payload, "no_secret_echo": raw_secret not in json.dumps(payload)}


def _probed_registry() -> TransportRegistry:
    registry = TransportRegistry()
    for manifest in default_wave7_manifests():
        registry.register(manifest)
    for probe in default_wave7_probes():
        registry.run_probe(probe)
    return registry


def _malformed_block() -> str:
    try:
        TransportAdapterManifest(
            transport_id="malformed.transport",
            kind=TransportKind.api,
            display_name="Malformed",
            capability_id="api.malformed",
            policy=TransportPolicy(
                policy_labels=(),
                authority_requirements=(
                    AuthorityRequirement(capability_id="api.malformed"),
                ),
            ),
        )
    except ValidationError:
        return "blocked"
    return "allowed"


def _duplicate_block() -> str:
    registry = TransportRegistry()
    manifest = default_wave7_manifests()[0]
    registry.register(manifest)
    try:
        registry.register(manifest)
    except TransportRegistryError as exc:
        return "blocked" if exc.reason == "duplicate_transport_id" else exc.reason
    return "allowed"


def _secret_block(raw_secret: str) -> str:
    try:
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
    except ValidationError:
        return "redacted"
    return "allowed"


def _unhealthy_enablement_block() -> str:
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
    result = registry.evaluate_live_enablement(
        _promotion_request(manifest.capability_id),
        authority=_authority(manifest.capability_id),
    )
    return "blocked" if result.reason == "unhealthy_probe" else result.reason


def _live_enablement_block() -> str:
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
    result = registry.evaluate_live_enablement(
        _promotion_request(manifest.capability_id),
        authority=_authority(manifest.capability_id),
    )
    return "blocked" if result.reason == "live_transport_not_authorized" else result.reason


def _promotion_request(capability_id: str) -> LiveTransportPromotionRequest:
    return LiveTransportPromotionRequest(
        promotion_id="promotion-wave7-provider",
        capability_id=capability_id,
        transport_kind="provider",
        idempotency_key="idem-wave7-provider",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(command="disable-live-transport", target=capability_id),
    )


def _authority(capability_id: str) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave7-principal",
        run_id="wave7-run",
        goal_contract_id="wave7-goal",
        capability_grants=[CapabilityGrant(capability_id=capability_id)],
    )


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True)
    return "sk-" not in serialized and "ghp_" not in serialized
