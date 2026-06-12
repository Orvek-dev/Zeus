from __future__ import annotations

import json

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorExecutionRequest,
    ConnectorExecutionRuntime,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleState,
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


def wave5_provider_payload() -> dict[str, object]:
    runtime = ProviderExecutionRuntime()
    local_route = runtime.prepare(
        ProviderExecutionRequest(
            provider="local",
            prompt="summarize local context",
            local_private=True,
            required_json_mode=True,
            required_streaming=True,
        ),
        _authority(["provider.local.generate"]),
    )
    external_envelope = runtime.prepare(
        ProviderExecutionRequest(
            provider="external",
            prompt="draft a plan",
            required_tool_calling=True,
            required_json_mode=True,
            network_host="api.openai.local",
            credential_scope="external.openai.readonly",
        ),
        _authority(
            ["provider.external.generate"],
            network_hosts=[
                ("provider.external.generate", "api.openai.local"),
            ],
            credential_scopes=[
                ("provider.external.generate", "external.openai.readonly"),
            ],
        ),
    )
    external_blocked = runtime.prepare(
        ProviderExecutionRequest(
            provider="external",
            prompt="draft a plan",
            network_host="api.openai.local",
            credential_scope="external.openai.readonly",
        ),
        _authority(
            ["provider.external.generate"],
            credential_scopes=[
                ("provider.external.generate", "external.openai.readonly"),
            ],
        ),
    )
    secret_block = runtime.prepare(
        ProviderExecutionRequest(
            provider="external",
            prompt="draft a plan",
            network_host="api.openai.local",
            credential_scope="ghp_TEST_FIXTURE",
        ),
        _authority(["provider.external.generate"]),
    )
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "no_raw_env_reads": True,
        "provider_kinds": ["fake", "local", "external"],
        "local_route": local_route.model_dump(mode="json"),
        "external_envelope": external_envelope.model_dump(mode="json"),
        "external_blocked": external_blocked.model_dump(mode="json"),
        "secret_block": secret_block.model_dump(mode="json"),
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def wave5_connector_payload() -> dict[str, object]:
    registry = _connector_registry()
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    registry.set_state("api-conn", ConnectorLifecycleState.healthy)
    registry.set_state("plugin-conn", ConnectorLifecycleState.healthy)
    runtime = ConnectorExecutionRuntime(registry)
    authority = _authority(
        ["mcp.echo", "api.fetch", "plugin.sync"],
        credential_scopes=[("api.fetch", "external.partner.readonly")],
    )
    mcp_execution = runtime.execute(
        ConnectorExecutionRequest(capability_id="mcp.echo"),
        authority,
    )
    api_execution = runtime.execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope="external.partner.readonly",
        ),
        authority,
    )
    plugin_execution = runtime.execute(
        ConnectorExecutionRequest(capability_id="plugin.sync"),
        authority,
    )
    unhealthy_registry = _connector_registry()
    unhealthy_registry.set_state("api-conn", ConnectorLifecycleState.unhealthy)
    unhealthy_block = ConnectorExecutionRuntime(unhealthy_registry).execute(
        ConnectorExecutionRequest(capability_id="api.fetch"),
        _authority(["api.fetch"]),
    )
    unauthorized_registry = _connector_registry()
    unauthorized_registry.set_state("plugin-conn", ConnectorLifecycleState.healthy)
    unauthorized_block = ConnectorExecutionRuntime(unauthorized_registry).execute(
        ConnectorExecutionRequest(capability_id="plugin.sync"),
        _authority([]),
    )
    secret_registry = _connector_registry()
    secret_registry.set_state("api-conn", ConnectorLifecycleState.healthy)
    secret_block = ConnectorExecutionRuntime(secret_registry).execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope="ghp_TEST_FIXTURE",
        ),
        _authority(["api.fetch"]),
    )
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "mcp_execution": mcp_execution.model_dump(mode="json"),
        "api_execution": api_execution.model_dump(mode="json"),
        "plugin_execution": plugin_execution.model_dump(mode="json"),
        "unhealthy_block": unhealthy_block.model_dump(mode="json"),
        "unauthorized_block": unauthorized_block.model_dump(mode="json"),
        "secret_block": secret_block.model_dump(mode="json"),
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def _authority(
    capability_ids: list[str],
    *,
    network_hosts: list[tuple[str, str]] | None = None,
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
    registry.register(
        ConnectorDeclaration(
            connector_id="plugin-conn",
            kind=ConnectorKind.plugin,
            display_name="Plugin Pack",
            descriptors=[_descriptor("plugin.sync")],
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


def _no_secret_echo(payload: dict[str, object]) -> bool:
    encoded = json.dumps(payload, sort_keys=True)
    return (
        "ghp_TEST_FIXTURE" not in encoded
        and "OPENAI_API_KEY" not in encoded
        and "sk-" not in encoded
    )
