"""Governed MCP capability layer (M3): de-whitelist via registry quarantine.

Replaces the hardcoded `mcp.echo`-only whitelist. Any MCP tool may register, but
its description is injection-scanned (rejected if poisoned), it lands quarantined
(every call needs approval until it earns active status), a schema change
re-quarantines it (registry rug-pull defense), and every call goes through the
single GovernedExecutionDispatcher chokepoint.
"""

from __future__ import annotations

from .gate import (
    MCPInvocation,
    MCPRegistration,
    invoke_mcp_tool,
    register_mcp_tool,
)
from .scanner import scan_tool_description

__all__ = [
    "MCPInvocation",
    "MCPRegistration",
    "invoke_mcp_tool",
    "register_mcp_tool",
    "scan_tool_description",
]
