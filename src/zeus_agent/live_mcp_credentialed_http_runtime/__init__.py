from zeus_agent.live_mcp_credentialed_http_runtime.models import LiveMcpCredentialedHttpResult


def __getattr__(name: str):
    if name == "LiveMcpCredentialedHttpRuntime":
        from zeus_agent.live_mcp_credentialed_http_runtime.runtime import LiveMcpCredentialedHttpRuntime

        return LiveMcpCredentialedHttpRuntime
    raise AttributeError(name)


__all__ = [
    "LiveMcpCredentialedHttpResult",
    "LiveMcpCredentialedHttpRuntime",
]
