from __future__ import annotations

import json

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleState,
)
from zeus_agent.connector_runtime.execution import (
    ConnectorExecutionRequest,
    ConnectorExecutionRuntime,
)
from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk
from zeus_agent.model_runtime.execution import (
    ProviderExecutionRequest,
    ProviderExecutionRuntime,
)
from zeus_agent.transport_runtime import (
    TransportRegistry,
    default_wave7_manifests,
    default_wave7_probes,
)
from zeus_agent.wave8_scenarios import wave8_runtime_integration_payload


def test_wave8_runtime_integration_scenario_blocks_registry_bypass() -> None:
    # Given: provider and connector runtime paths are registry-bound.
    raw_secret = "ghp_TEST_FIXTURE"

    # When: allowed and adversarial execution attempts run.
    payload = wave8_runtime_integration_payload(raw_secret=raw_secret)

    # Then: healthy dry-run paths pass and unsafe paths block before side effects.
    assert payload["registry_gate"] == "enabled"
    assert payload["healthy_provider_allowed"] is True
    assert payload["healthy_connector_allowed"] is True
    assert payload["unknown_transport"] == "blocked"
    assert payload["unhealthy_probe"] == "blocked"
    assert payload["transport_kind_mismatch"] == "blocked"
    assert payload["live_transport_not_authorized"] == "blocked"
    assert payload["secret_like_credential_scope"] == "redacted"
    assert payload["blocked_handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_provider_runtime_checks_transport_registry_before_route_selection() -> None:
    # Given: a healthy external provider transport manifest and matching authority.
    runtime = ProviderExecutionRuntime(transport_registry=_probed_registry())
    capability_id = "provider.external.generate"
    request = ProviderExecutionRequest(
        provider="external",
        prompt="draft a registry-bound plan",
        required_json_mode=True,
        network_host="api.openai.local",
        credential_scope="external.openai.readonly",
    )

    # When: provider preparation runs.
    result = runtime.prepare(
        request,
        _authority(
            [capability_id],
            network_hosts=[(capability_id, "api.openai.local")],
            credential_scopes=[(capability_id, "external.openai.readonly")],
        ),
    )

    # Then: registry health and kind checks allow only a dry-run envelope.
    assert result.decision == "selected"
    assert result.envelope is not None
    assert result.envelope.provider == "external"
    assert result.envelope.transport == "dry_run"
    assert result.envelope.side_effects is False


def test_connector_runtime_blocks_unhealthy_transport_before_handler() -> None:
    # Given: lifecycle marks the API connector healthy but transport probe is unhealthy.
    lifecycle = _connector_registry()
    lifecycle.set_state("api-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(lifecycle, transport_registry=_probed_registry())

    # When: the API connector is invoked.
    result = runtime.execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope="external.partner.readonly",
        ),
        _authority(
            ["api.fetch"],
            credential_scopes=[("api.fetch", "external.partner.readonly")],
        ),
    )

    # Then: transport health blocks before the execution handler can run.
    assert result.decision == "blocked"
    assert result.reason == "unhealthy_probe"
    assert result.handler_executed is False
    assert result.envelope is None


def test_connector_runtime_allows_healthy_registry_bound_mcp_dry_run() -> None:
    # Given: lifecycle and transport registry both mark MCP healthy.
    lifecycle = _connector_registry()
    lifecycle.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(lifecycle, transport_registry=_probed_registry())

    # When: the MCP connector is invoked through the registry-bound runtime.
    result = runtime.execute(
        ConnectorExecutionRequest(capability_id="mcp.echo"),
        _authority(["mcp.echo"]),
    )

    # Then: the handler executes only after registry and broker gates pass.
    assert result.decision == "allowed"
    assert result.handler_executed is True
    assert result.envelope is not None
    assert result.envelope.connector_kind == "mcp"
    assert result.envelope.transport == "dry_run"


def _probed_registry() -> TransportRegistry:
    registry = TransportRegistry()
    for manifest in default_wave7_manifests():
        registry.register(manifest)
    for probe in default_wave7_probes():
        registry.run_probe(probe)
    return registry


def _connector_registry() -> ConnectorLifecycleRegistry:
    registry = ConnectorLifecycleRegistry()
    registry.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo")],
        )
    )
    registry.register(
        ConnectorDeclaration(
            connector_id="api-conn",
            kind=ConnectorKind.api,
            display_name="Partner API",
            descriptors=[_descriptor("api.fetch")],
        )
    )
    return registry


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def _authority(
    capability_ids: list[str],
    *,
    network_hosts: list[tuple[str, str]] | None = None,
    credential_scopes: list[tuple[str, str]] | None = None,
) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave8-principal",
        run_id="wave8-run",
        goal_contract_id="wave8-goal",
        capability_grants=[
            CapabilityGrant(capability_id=capability_id)
            for capability_id in capability_ids
        ],
        network_grants=[
            NetworkGrant(capability_id=capability_id, network_host=network_host)
            for capability_id, network_host in network_hosts or []
        ],
        credential_grants=[
            CredentialGrant(
                capability_id=capability_id,
                credential_scope=credential_scope,
            )
            for capability_id, credential_scope in credential_scopes or []
        ],
    )
