from zeus_agent.live_gateway_credentialed_http_runtime.models import LiveGatewayCredentialedHttpResult


def __getattr__(name: str):
    if name == "LiveGatewayCredentialedHttpRuntime":
        from zeus_agent.live_gateway_credentialed_http_runtime.runtime import LiveGatewayCredentialedHttpRuntime

        return LiveGatewayCredentialedHttpRuntime
    raise AttributeError(name)


__all__ = [
    "LiveGatewayCredentialedHttpResult",
    "LiveGatewayCredentialedHttpRuntime",
]
