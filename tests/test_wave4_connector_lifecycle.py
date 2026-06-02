from __future__ import annotations

from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleRuntime,
    ConnectorLifecycleState,
)


def _authority(capability_ids: list[str]) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave4-principal",
        run_id="wave4-run",
        goal_contract_id="wave4-goal",
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
    )


def _descriptor(capability_id: str, name: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=name,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def test_connector_lifecycle_reports_discovered_tools_and_model_visible_subset() -> None:
    # Given: three declared connectors and one untouched connector that remains registered.
    runtime = ConnectorLifecycleRuntime()
    runtime.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo", "mcp.echo")],
        )
    )
    runtime.register(
        ConnectorDeclaration(
            connector_id="api-conn",
            kind=ConnectorKind.api,
            display_name="Partner API",
            descriptors=[_descriptor("api.fetch", "api.fetch")],
        )
    )
    runtime.register(
        ConnectorDeclaration(
            connector_id="plugin-conn",
            kind=ConnectorKind.plugin,
            display_name="Plugin Pack",
            descriptors=[_descriptor("plugin.sync", "plugin.sync")],
        )
    )
    runtime.register(
        ConnectorDeclaration(
            connector_id="registered-conn",
            kind=ConnectorKind.api,
            display_name="Registered Only",
            descriptors=[_descriptor("registered.scan", "registered.scan")],
        )
    )
    runtime.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    runtime.set_state("api-conn", ConnectorLifecycleState.unhealthy)
    runtime.set_state("plugin-conn", ConnectorLifecycleState.disabled)

    # When: lifecycle and model-visible tools are compiled through CapabilityGraph.
    report = runtime.lifecycle_report()
    discovered = runtime.discovered_tool_names()
    graph = runtime.build_capability_graph()
    visible = graph.compile_model_schema(
        profile="coding-agent",
        authority=_authority(["mcp.echo", "api.fetch"]),
    )

    # Then: lifecycle states and tool visibility follow Wave4 authority and health rules.
    assert report == {
        "mcp-conn": "healthy",
        "api-conn": "unhealthy",
        "plugin-conn": "disabled",
        "registered-conn": "registered",
    }
    assert discovered == ["api.fetch", "mcp.echo", "plugin.sync", "registered.scan"]
    assert [entry["function"]["name"] for entry in visible] == ["mcp.echo"]


def test_broker_dispatch_allows_healthy_connector_and_blocks_unhealthy_before_handler() -> None:
    # Given: a healthy MCP connector and an unhealthy API connector with broker handlers.
    runtime = ConnectorLifecycleRuntime()
    runtime.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo", "mcp.echo")],
        )
    )
    runtime.register(
        ConnectorDeclaration(
            connector_id="api-conn",
            kind=ConnectorKind.api,
            display_name="Partner API",
            descriptors=[_descriptor("api.fetch", "api.fetch")],
        )
    )
    runtime.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    runtime.set_state("api-conn", ConnectorLifecycleState.unhealthy)

    graph = runtime.build_capability_graph()
    handlers = runtime.build_stub_handlers()
    unhealthy_called = {"count": 0}
    original_unhealthy_handler = handlers["api.fetch"]

    def tracked_unhealthy_handler(payload: dict[str, object]) -> object:
        unhealthy_called["count"] += 1
        return original_unhealthy_handler(payload)

    handlers["api.fetch"] = tracked_unhealthy_handler
    broker = CapabilityBroker(graph=graph, handlers=handlers)
    authority = _authority(["mcp.echo", "api.fetch"])

    # When: the healthy and unhealthy connector tools are dispatched.
    healthy_response = broker.dispatch(
        capability_id="mcp.echo",
        payload={},
        context=authority,
    )
    unhealthy_response = broker.dispatch(
        capability_id="api.fetch",
        payload={},
        context=authority,
    )

    # Then: healthy tools return stubs and unhealthy tools are blocked pre-dispatch.
    assert healthy_response["decision"] == "allowed"
    assert healthy_response["result"] == {
        "connector_id": "mcp-conn",
        "capability_id": "mcp.echo",
        "side_effects": False,
    }
    assert healthy_response["evidence"]["status"] == "pass"

    assert unhealthy_response["decision"] == "blocked"
    assert unhealthy_response["reason"] == "capability_not_model_visible"
    assert unhealthy_response["evidence"]["status"] == "blocked"
    assert unhealthy_called["count"] == 0


def test_connector_lifecycle_registry_class_name_works_with_runtime_alias() -> None:
    # Given: canonical and compatibility class names from connector runtime exports.
    runtime = ConnectorLifecycleRuntime()
    registry = ConnectorLifecycleRegistry()

    # Then: both names resolve to the same lifecycle implementation type.
    assert isinstance(runtime, ConnectorLifecycleRegistry)
    assert isinstance(registry, ConnectorLifecycleRuntime)


def test_reregister_same_connector_id_is_idempotent_and_updates_state_deterministically() -> None:
    # Given: a connector declaration is first registered and then set healthy.
    registry = ConnectorLifecycleRegistry()
    first_declaration = ConnectorDeclaration(
        connector_id="mcp-conn",
        kind=ConnectorKind.mcp,
        display_name="Local MCP",
        descriptors=[_descriptor("mcp.echo", "mcp.echo")],
    )
    replacement_declaration = ConnectorDeclaration(
        connector_id="mcp-conn",
        kind=ConnectorKind.mcp,
        display_name="Local MCP Updated",
        descriptors=[_descriptor("mcp.ping", "mcp.ping")],
    )
    registry.register(first_declaration)
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)

    # When: the same connector_id is registered again with a replacement declaration.
    registry.register(replacement_declaration)

    # Then: registration is idempotent, declaration updates, and state is deterministically reset.
    assert registry.lifecycle_report() == {"mcp-conn": "registered"}
    assert registry.discovered_tool_names() == ["mcp.ping"]


def test_stale_broker_blocks_connector_after_lifecycle_state_changes() -> None:
    # Given: a broker built while a connector was healthy.
    registry = ConnectorLifecycleRegistry()
    registry.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo", "mcp.echo")],
        )
    )
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    graph = registry.build_capability_graph()
    handlers = registry.build_stub_handlers()
    handler_calls = {"count": 0}
    original_handler = handlers["mcp.echo"]

    def tracked_handler(payload: dict[str, object]) -> object:
        handler_calls["count"] += 1
        return original_handler(payload)

    handlers["mcp.echo"] = tracked_handler
    broker = CapabilityBroker(graph=graph, handlers=handlers)
    authority = _authority(["mcp.echo"])

    # When: the connector is disabled after graph/broker construction.
    registry.set_state("mcp-conn", ConnectorLifecycleState.disabled)
    response = broker.dispatch(capability_id="mcp.echo", payload={}, context=authority)

    # Then: the live lifecycle graph blocks before the stale handler is invoked.
    assert response["decision"] == "blocked"
    assert response["reason"] == "capability_not_model_visible"
    assert response["evidence"]["status"] == "blocked"
    assert handler_calls["count"] == 0
