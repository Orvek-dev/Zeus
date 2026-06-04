from __future__ import annotations

from zeus_agent.agent_runtime.live_loop_support import CAPABILITY_ID, MAX_ECHO_TEXT_LENGTH, TOOL_NAME
from zeus_agent.tool_runtime import ToolDefinition, ToolRuntimeRegistry, ToolsetDefinition


def build_local_echo_tool_runtime() -> ToolRuntimeRegistry:
    runtime = ToolRuntimeRegistry()
    runtime.register_toolset(
        ToolsetDefinition(
            toolset_id="wave15.tools",
            display_name="Wave15 Tools",
            tools=(
                ToolDefinition(
                    name=TOOL_NAME,
                    description="Record local Wave15 live-agent evidence",
                    capability_id=CAPABILITY_ID,
                    input_schema={
                        "type": "object",
                        "properties": {"text": {"type": "string", "maxLength": MAX_ECHO_TEXT_LENGTH}},
                    },
                ),
            ),
        ),
        handlers={TOOL_NAME: _local_echo},
    )
    return runtime


def _local_echo(payload: dict) -> dict[str, str]:
    text = str(payload["text"])
    if len(text) > MAX_ECHO_TEXT_LENGTH:
        return {"decision": "blocked", "reason": "tool_input_too_large"}
    return {"echo": text, "source": "wave15"}


__all__ = ["build_local_echo_tool_runtime"]
