"""Gate 2 — the MCP gateway (P4).

The host connects to ONE MCP server (Zeus); Zeus is a governed client to the
real downstream servers. Imported tools land quarantined, de-quarantine is an
operator review, schema drift re-quarantines (rug-pull defense), and tool
results are scanned for injection — a hit taints the session.
"""

from __future__ import annotations

from .gateway import (
    DownstreamServer,
    GatewaySession,
    McpCallOutcome,
    McpGateway,
    SyncReport,
)
from .scan import scan_for_injection
from .stdio import StdioMcpClient, serve_stdio

__all__ = [
    "DownstreamServer",
    "GatewaySession",
    "McpCallOutcome",
    "McpGateway",
    "StdioMcpClient",
    "SyncReport",
    "scan_for_injection",
    "serve_stdio",
]
