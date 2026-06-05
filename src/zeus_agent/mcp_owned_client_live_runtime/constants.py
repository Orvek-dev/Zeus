from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

TARGET_VERSION: Final = "v1.0.0-rc.9"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.9.mcp_owned_client_live"
NOW: Final = datetime(2026, 6, 6, 5, 0, tzinfo=timezone.utc)
EXPIRES_AT: Final = datetime(2026, 6, 7, 5, 0, tzinfo=timezone.utc)
DEFAULT_ENDPOINT: Final = "https://mcp.github.local/rpc"
DEFAULT_ALLOWED_HOST: Final = "mcp.github.local"
DEFAULT_SECRET_REF: Final = "env://ZEUS_RC9_MCP_TOKEN"
DEFAULT_SERVER_ID: Final = "mcp.github"
DEFAULT_TOOL_NAME: Final = "repo.search"
DEFAULT_QUERY: Final = "Zeus MCP owned client live checkpoint"
MCP_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "mcp_remote_tool",
)
MCP_LIVE_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "mcp_remote_tool",
    "live_transport",
    "owned_client_adapter",
)
