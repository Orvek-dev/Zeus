from __future__ import annotations

from zeus_agent.tool_runtime import ToolExecutionRequest, ToolRuntimeRegistry
from zeus_agent.transport_runtime import TransportHealth, TransportKind
from wave11_tool_fixtures import (
    EXPIRES_AT,
    ISSUED_AT,
    lease,
    local_tool,
    registry,
    toolset,
)


def test_wave11_blocks_disabled_unknown_and_malformed_boundaries() -> None:
    # Given: a registered toolset that can be disabled and untrusted boundary payloads.
    runtime = ToolRuntimeRegistry()
    runtime.register_toolset(
        toolset(local_tool()),
        handlers={"local.echo": lambda payload: {"ok": payload["text"]}},
    )
    runtime_lease = lease("api.tool.echo")

    # When: disabled, unknown, malformed MCP, and malformed tool-call paths are inspected.
    runtime.disable("wave11.tools")
    disabled = runtime.execute(
        ToolExecutionRequest(tool_name="local.echo", arguments={"text": "blocked"}),
        runtime_lease,
        now=ISSUED_AT,
    )
    unknown = runtime.execute(
        ToolExecutionRequest(tool_name="missing.tool", arguments={}),
        runtime_lease,
        now=ISSUED_AT,
    )
    malformed_discovery = runtime.inspect_mcp_discovery(
        {"server_id": "wave11.mcp", "tools": []},
    )
    malformed_call = runtime.inspect_untrusted_call(
        {"name": "local.echo", "arguments": "{not-json"},
        runtime_lease,
        now=ISSUED_AT,
    )

    # Then: every unsafe boundary fails closed before handlers or networks can run.
    assert disabled.decision == "blocked"
    assert disabled.reason == "disabled_toolset"
    assert disabled.handler_executed is False
    assert unknown.decision == "blocked"
    assert unknown.reason == "unknown_tool"
    assert malformed_discovery.decision == "blocked"
    assert malformed_discovery.reason == "malformed_mcp_discovery"
    assert malformed_call.decision == "blocked"
    assert malformed_call.reason == "malformed_tool_json"
    assert malformed_call.handler_executed is False


def test_wave11_blocks_missing_expired_widened_and_over_budget_leases() -> None:
    # Given: a local tool registered without transport side effects.
    runtime = ToolRuntimeRegistry()
    runtime.register_toolset(
        toolset(local_tool()),
        handlers={"local.echo": lambda payload: {"ok": payload["text"]}},
    )
    request = ToolExecutionRequest(tool_name="local.echo", arguments={"text": "x"})

    # When: lease state is missing, expired, widened, or over the allowed budget.
    missing = runtime.execute(request, None, now=ISSUED_AT)
    expired = runtime.execute(request, lease("api.tool.echo"), now=EXPIRES_AT)
    widened = runtime.execute(request, lease("mcp.echo"), now=ISSUED_AT)
    over_budget = runtime.execute(
        ToolExecutionRequest(
            tool_name="local.echo",
            arguments={"text": "x"},
            budget_required=101,
        ),
        lease("api.tool.echo", budget_limit=100),
        now=ISSUED_AT,
    )

    # Then: lease governance blocks each case before broker handler dispatch.
    assert missing.reason == "missing_runtime_lease"
    assert missing.handler_executed is False
    assert expired.reason == "runtime_lease_expired"
    assert expired.handler_executed is False
    assert widened.reason == "authority_widening"
    assert widened.handler_executed is False
    assert over_budget.reason == "over_budget"
    assert over_budget.handler_executed is False


def test_wave11_blocks_transport_mismatch_and_unhealthy_transport() -> None:
    # Given: registry-bound local tools with bad transport kind and bad health fixtures.
    mismatch_runtime = ToolRuntimeRegistry(transport_registry=registry(
        ("api.tool.echo", TransportKind.mcp, TransportHealth.healthy),
    ))
    mismatch_runtime.register_toolset(
        toolset(local_tool()),
        handlers={"local.echo": lambda payload: {"ok": payload["text"]}},
    )
    unhealthy_runtime = ToolRuntimeRegistry(transport_registry=registry(
        ("api.tool.echo", TransportKind.api, TransportHealth.unhealthy),
    ))
    unhealthy_runtime.register_toolset(
        toolset(local_tool()),
        handlers={"local.echo": lambda payload: {"ok": payload["text"]}},
    )
    request = ToolExecutionRequest(tool_name="local.echo", arguments={"text": "x"})
    runtime_lease = lease("api.tool.echo")

    # When: execution evaluates transport registry state before broker dispatch.
    mismatch = mismatch_runtime.execute(request, runtime_lease, now=ISSUED_AT)
    unhealthy = unhealthy_runtime.execute(request, runtime_lease, now=ISSUED_AT)

    # Then: bad transport state blocks without invoking handlers.
    assert mismatch.decision == "blocked"
    assert mismatch.reason == "transport_kind_mismatch"
    assert mismatch.handler_executed is False
    assert unhealthy.decision == "blocked"
    assert unhealthy.reason == "unhealthy_probe"
    assert unhealthy.handler_executed is False


def test_wave11_redacts_secret_like_handler_results() -> None:
    # Given: a handler that returns secret-like strings.
    runtime = ToolRuntimeRegistry()
    raw_secret = "ghp_TEST_FIXTURE"
    runtime.register_toolset(
        toolset(local_tool()),
        handlers={
            "local.echo": lambda payload: {
                "token": raw_secret,
                "nested": ["password=abc123"],
            },
        },
    )

    # When: execution succeeds through lease and broker governance.
    result = runtime.execute(
        ToolExecutionRequest(tool_name="local.echo", arguments={"text": "x"}),
        lease("api.tool.echo"),
        now=ISSUED_AT,
    )

    # Then: the raw secret never appears in the returned boundary model.
    serialized = result.model_dump_json()
    assert result.decision == "allowed"
    assert raw_secret not in serialized
    assert "password=abc123" not in serialized
    assert "[redacted-secret]" in serialized
    assert result.no_secret_echo is True
