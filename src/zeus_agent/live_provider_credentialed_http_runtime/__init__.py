from zeus_agent.live_provider_credentialed_http_runtime.models import LiveProviderCredentialedHttpResult


def __getattr__(name: str):
    if name == "LiveProviderCredentialedHttpRuntime":
        from zeus_agent.live_provider_credentialed_http_runtime.runtime import LiveProviderCredentialedHttpRuntime

        return LiveProviderCredentialedHttpRuntime
    raise AttributeError(name)


__all__ = [
    "LiveProviderCredentialedHttpResult",
    "LiveProviderCredentialedHttpRuntime",
]
