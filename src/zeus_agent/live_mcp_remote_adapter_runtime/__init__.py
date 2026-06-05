from zeus_agent.live_mcp_remote_adapter_runtime.models import (
    LiveMcpRemoteAdapterClient,
    LiveMcpRemoteAdapterReceipt,
    LiveMcpRemoteAdapterRequest,
    LiveMcpRemoteAdapterResult,
    StaticMcpRemoteAdapterClient,
)


def __getattr__(name: str):
    if name == "LiveMcpRemoteAdapterRuntime":
        from zeus_agent.live_mcp_remote_adapter_runtime.runtime import LiveMcpRemoteAdapterRuntime

        return LiveMcpRemoteAdapterRuntime
    raise AttributeError(name)


__all__ = [
    "LiveMcpRemoteAdapterClient",
    "LiveMcpRemoteAdapterReceipt",
    "LiveMcpRemoteAdapterRequest",
    "LiveMcpRemoteAdapterResult",
    "LiveMcpRemoteAdapterRuntime",
    "StaticMcpRemoteAdapterClient",
]
