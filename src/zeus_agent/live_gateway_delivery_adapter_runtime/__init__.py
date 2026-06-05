from zeus_agent.live_gateway_delivery_adapter_runtime.models import (
    LiveGatewayDeliveryAdapterClient,
    LiveGatewayDeliveryAdapterReceipt,
    LiveGatewayDeliveryAdapterRequest,
    LiveGatewayDeliveryAdapterResult,
    StaticGatewayDeliveryAdapterClient,
)


def __getattr__(name: str):
    if name == "LiveGatewayDeliveryAdapterRuntime":
        from zeus_agent.live_gateway_delivery_adapter_runtime.runtime import LiveGatewayDeliveryAdapterRuntime

        return LiveGatewayDeliveryAdapterRuntime
    raise AttributeError(name)


__all__ = [
    "LiveGatewayDeliveryAdapterClient",
    "LiveGatewayDeliveryAdapterReceipt",
    "LiveGatewayDeliveryAdapterRequest",
    "LiveGatewayDeliveryAdapterResult",
    "LiveGatewayDeliveryAdapterRuntime",
    "StaticGatewayDeliveryAdapterClient",
]
