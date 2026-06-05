from zeus_agent.live_provider_direct_adapter_runtime.models import (
    LiveProviderDirectAdapterClient,
    LiveProviderDirectAdapterReceipt,
    LiveProviderDirectAdapterRequest,
    LiveProviderDirectAdapterResult,
    StaticProviderDirectAdapterClient,
)


def __getattr__(name: str):
    if name == "LiveProviderDirectAdapterRuntime":
        from zeus_agent.live_provider_direct_adapter_runtime.runtime import LiveProviderDirectAdapterRuntime

        return LiveProviderDirectAdapterRuntime
    raise AttributeError(name)

__all__ = [
    "LiveProviderDirectAdapterClient",
    "LiveProviderDirectAdapterReceipt",
    "LiveProviderDirectAdapterRequest",
    "LiveProviderDirectAdapterResult",
    "LiveProviderDirectAdapterRuntime",
    "StaticProviderDirectAdapterClient",
]
