from __future__ import annotations

from zeus_agent.transport_runtime import (
    SandboxProbeDefinition,
    TransportHealth,
    TransportRegistry,
    default_wave7_manifests,
    default_wave7_probes,
)
from zeus_agent.wave7_scenarios import wave7_transport_registry_payload


def test_wave7_registers_transport_manifests_with_policy_and_probe_state() -> None:
    # Given: provider, MCP, API, and plugin transport manifests.
    payload = wave7_transport_registry_payload()

    # When: the registry scenario runs deterministic sandbox probes.
    manifests = payload["manifests"]
    health = payload["health"]

    # Then: every adapter is policy-bound, dry-run probed, and live-disabled.
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True
    assert payload["sandbox_probe_count"] == 4
    assert payload["live_transport"] is False
    assert {manifest["kind"] for manifest in manifests} == {
        "provider",
        "mcp",
        "api",
        "plugin",
    }
    assert {manifest["transport_id"] for manifest in manifests} == {
        "provider.external.openai",
        "mcp.local.echo",
        "api.partner.fetch",
        "plugin.pack.sync",
    }
    assert all(manifest["live_transport"] is False for manifest in manifests)
    assert all(manifest["policy_labels"] for manifest in manifests)
    assert all(manifest["authority_requirements"] for manifest in manifests)
    assert health["provider.external.openai"] == "healthy"
    assert health["mcp.local.echo"] == "healthy"
    assert health["api.partner.fetch"] == "unhealthy"
    assert health["plugin.pack.sync"] == "healthy"


def test_transport_registry_probe_updates_health_without_side_effects() -> None:
    # Given: a fresh transport registry with deterministic fixture manifests.
    registry = TransportRegistry()
    for manifest in default_wave7_manifests():
        registry.register(manifest)

    # When: sandbox probes run for every transport.
    receipts = [registry.run_probe(probe) for probe in default_wave7_probes()]

    # Then: probe receipts update health and never execute handlers or network.
    assert len(receipts) == 4
    assert receipts[0].health == TransportHealth.healthy
    assert all(receipt.handler_executed is False for receipt in receipts)
    assert all(receipt.network_opened is False for receipt in receipts)
    assert all(receipt.side_effects is False for receipt in receipts)
    assert registry.health_report()["api.partner.fetch"] == "unhealthy"


def test_transport_registry_rejects_unknown_probe_without_mutating_health() -> None:
    # Given: a registry with known fixtures and no probe state.
    registry = TransportRegistry()
    for manifest in default_wave7_manifests():
        registry.register(manifest)

    # When: a sandbox probe references an unknown transport id.
    result = registry.blocked_probe(
        SandboxProbeDefinition(
            probe_id="probe-unknown",
            transport_id="missing.transport",
            expected_health=TransportHealth.healthy,
        )
    )

    # Then: the block is explicit and registered health remains unknown.
    assert result.reason == "unknown_transport_id"
    assert result.handler_executed is False
    assert result.network_opened is False
    assert registry.health_report()["provider.external.openai"] == "unknown"
