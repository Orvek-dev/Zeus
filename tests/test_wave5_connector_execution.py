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
)
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def _registry() -> ConnectorLifecycleRegistry:
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
    registry.register(
        ConnectorDeclaration(
            connector_id="plugin-conn",
            kind=ConnectorKind.plugin,
            display_name="Plugin Pack",
            descriptors=[_descriptor("plugin.sync")],
        )
    )
    return registry


def _authority(
    capability_ids: list[str],
    *,
    credential_scopes: list[tuple[str, str]] | None = None,
) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave5-principal",
        run_id="wave5-run",
        goal_contract_id="wave5-goal",
        capability_grants=[
            CapabilityGrant(capability_id=capability_id)
            for capability_id in capability_ids
        ],
        credential_grants=[
            CredentialGrant(
                capability_id=capability_id,
                credential_scope=credential_scope,
            )
            for capability_id, credential_scope in credential_scopes or []
        ],
    )


def test_connector_execution_builds_dry_run_envelopes_for_mcp_api_and_plugin() -> None:
    # Given: healthy MCP/API/plugin connectors and matching authority.
    registry = _registry()
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    registry.set_state("api-conn", ConnectorLifecycleState.healthy)
    registry.set_state("plugin-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(registry)
    authority = _authority(
        ["mcp.echo", "api.fetch", "plugin.sync"],
        credential_scopes=[("api.fetch", "external.partner.readonly")],
    )

    # When: each connector kind is invoked through the execution runtime.
    mcp = runtime.execute(
        ConnectorExecutionRequest(capability_id="mcp.echo"),
        authority,
    )
    api = runtime.execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope="external.partner.readonly",
        ),
        authority,
    )
    plugin = runtime.execute(
        ConnectorExecutionRequest(capability_id="plugin.sync"),
        authority,
    )

    # Then: broker-mediated dry-run envelopes are emitted without external effects.
    assert mcp.decision == "allowed"
    assert mcp.handler_executed is True
    assert mcp.envelope is not None
    assert mcp.envelope.connector_kind == "mcp"
    assert mcp.envelope.dry_run is True
    assert mcp.envelope.side_effects is False

    assert api.decision == "allowed"
    assert api.handler_executed is True
    assert api.envelope is not None
    assert api.envelope.connector_kind == "api"
    assert api.envelope.credential_scope_label == "external.partner.readonly"
    assert api.envelope.dry_run is True
    assert api.envelope.side_effects is False

    assert plugin.decision == "allowed"
    assert plugin.handler_executed is True
    assert plugin.envelope is not None
    assert plugin.envelope.connector_kind == "plugin"
    assert plugin.envelope.dry_run is True
    assert plugin.envelope.side_effects is False


def test_connector_execution_blocks_unhealthy_connector_before_handler() -> None:
    # Given: an unhealthy API connector that still has authority.
    registry = _registry()
    registry.set_state("api-conn", ConnectorLifecycleState.unhealthy)
    runtime = ConnectorExecutionRuntime(registry)
    authority = _authority(["api.fetch"])

    # When: the unhealthy connector is invoked.
    result = runtime.execute(
        ConnectorExecutionRequest(capability_id="api.fetch"),
        authority,
    )

    # Then: CapabilityBroker blocks before the execution handler can run.
    assert result.decision == "blocked"
    assert result.reason == "capability_not_model_visible"
    assert result.handler_executed is False
    assert result.envelope is None
    assert result.broker_response["evidence"]["status"] == "blocked"


def test_connector_execution_blocks_unauthorized_connector_before_handler() -> None:
    # Given: a healthy plugin connector with no matching capability authority.
    registry = _registry()
    registry.set_state("plugin-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(registry)

    # When: the connector is invoked without a grant.
    result = runtime.execute(
        ConnectorExecutionRequest(capability_id="plugin.sync"),
        _authority([]),
    )

    # Then: the model-visible schema excludes it and the handler is not called.
    assert result.decision == "blocked"
    assert result.reason == "capability_not_model_visible"
    assert result.handler_executed is False
    assert result.envelope is None


def test_connector_execution_rejects_secret_like_credential_scope_without_echoing_it() -> None:
    # Given: a secret-like value mistakenly supplied as a connector credential scope.
    raw_secret = "ghp_TEST_FIXTURE"
    registry = _registry()
    registry.set_state("api-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(registry)

    # When: connector execution parses the credential boundary.
    result = runtime.execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope=raw_secret,
        ),
        _authority(["api.fetch"]),
    )

    # Then: the raw secret is not present in the structured result.
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.decision == "blocked"
    assert result.reason == "secret_like_credential_scope"
    assert result.handler_executed is False
    assert result.envelope is None
    assert raw_secret not in serialized
