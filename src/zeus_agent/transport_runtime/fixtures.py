from __future__ import annotations

from typing import Optional

from zeus_agent.transport_runtime.manifest import (
    AuthorityRequirement,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
)
from zeus_agent.transport_runtime.probes import SandboxProbeDefinition


def default_wave7_manifests() -> list[TransportAdapterManifest]:
    return [
        _manifest(
            transport_id="provider.external.openai",
            kind=TransportKind.provider,
            display_name="External OpenAI Provider",
            capability_id="provider.external.generate",
            policy_labels=("external-ai", "provider"),
            credential_scope="external.openai.readonly",
            network_host="api.openai.local",
            probe_id="probe-provider-openai",
        ),
        _manifest(
            transport_id="mcp.local.echo",
            kind=TransportKind.mcp,
            display_name="Local MCP Echo",
            capability_id="mcp.echo",
            policy_labels=("mcp", "local"),
            probe_id="probe-mcp-echo",
        ),
        _manifest(
            transport_id="api.partner.fetch",
            kind=TransportKind.api,
            display_name="Partner API Fetch",
            capability_id="api.fetch",
            policy_labels=("external-api", "api"),
            credential_scope="external.partner.readonly",
            network_host="api.partner.local",
            probe_id="probe-api-partner",
        ),
        _manifest(
            transport_id="plugin.pack.sync",
            kind=TransportKind.plugin,
            display_name="Plugin Pack Sync",
            capability_id="plugin.sync",
            policy_labels=("plugin", "local"),
            probe_id="probe-plugin-sync",
        ),
    ]


def default_wave7_probes() -> list[SandboxProbeDefinition]:
    return [
        SandboxProbeDefinition(
            probe_id="probe-provider-openai",
            transport_id="provider.external.openai",
            expected_health=TransportHealth.healthy,
        ),
        SandboxProbeDefinition(
            probe_id="probe-mcp-echo",
            transport_id="mcp.local.echo",
            expected_health=TransportHealth.healthy,
        ),
        SandboxProbeDefinition(
            probe_id="probe-api-partner",
            transport_id="api.partner.fetch",
            expected_health=TransportHealth.unhealthy,
        ),
        SandboxProbeDefinition(
            probe_id="probe-plugin-sync",
            transport_id="plugin.pack.sync",
            expected_health=TransportHealth.healthy,
        ),
    ]


def default_wave8_manifests() -> list[TransportAdapterManifest]:
    return default_wave7_manifests()


def default_wave8_probes() -> list[SandboxProbeDefinition]:
    return default_wave7_probes()


def _manifest(
    *,
    transport_id: str,
    kind: TransportKind,
    display_name: str,
    capability_id: str,
    policy_labels: tuple[str, ...],
    probe_id: str,
    credential_scope: Optional[str] = None,
    network_host: Optional[str] = None,
) -> TransportAdapterManifest:
    requirement = AuthorityRequirement(
        capability_id=capability_id,
        network_host=network_host,
        credential_scope=credential_scope,
    )
    return TransportAdapterManifest(
        transport_id=transport_id,
        kind=kind,
        display_name=display_name,
        capability_id=capability_id,
        policy=TransportPolicy(
            policy_labels=policy_labels,
            authority_requirements=(requirement,),
            credential_scope_label=credential_scope,
        ),
        sandbox_probe_ids=(probe_id,),
    )
