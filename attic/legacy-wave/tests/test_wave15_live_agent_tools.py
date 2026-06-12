from __future__ import annotations

from zeus_agent.agent_runtime.live_loop_support import MAX_ECHO_TEXT_LENGTH
from zeus_agent.live_agent_loop import LiveAgentLoop
from zeus_agent.live_agent_loop.tools import build_local_echo_tool_runtime
from zeus_agent.tool_runtime import ToolExecutionRequest


def test_live_agent_local_tool_runtime_requires_lease_and_records_evidence(tmp_path) -> None:
    runtime = LiveAgentLoop(tmp_path)
    tool_runtime = build_local_echo_tool_runtime()

    blocked = tool_runtime.execute(
        ToolExecutionRequest(tool_name="local.echo", arguments={"text": "hello"}),
        None,
        now=runtime.tool_lease().issued_at,
    )
    allowed = tool_runtime.execute(
        ToolExecutionRequest(tool_name="local.echo", arguments={"text": "hello"}),
        runtime.tool_lease(),
        now=runtime.tool_lease().issued_at,
    )

    assert blocked.decision == "blocked"
    assert blocked.handler_executed is False
    assert allowed.decision == "allowed"
    assert allowed.handler_executed is True
    assert allowed.evidence is not None


def test_live_agent_local_tool_runtime_bounds_echo_text(tmp_path) -> None:
    runtime = LiveAgentLoop(tmp_path)
    tool_runtime = build_local_echo_tool_runtime()
    schema = tool_runtime.compile_model_schema(runtime.tool_lease(), now=runtime.tool_lease().issued_at)

    oversized = tool_runtime.execute(
        ToolExecutionRequest(
            tool_name="local.echo",
            arguments={"text": "x" * (MAX_ECHO_TEXT_LENGTH + 1)},
        ),
        runtime.tool_lease(),
        now=runtime.tool_lease().issued_at,
    )

    text_schema = schema[0]["function"]["parameters"]["properties"]["text"]
    assert text_schema["maxLength"] == MAX_ECHO_TEXT_LENGTH
    assert oversized.decision == "blocked"
    assert oversized.reason == "tool_input_too_large"
    assert oversized.result is not None
    assert "echo" not in oversized.result
