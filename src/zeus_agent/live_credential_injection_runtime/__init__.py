from zeus_agent.live_credential_injection_runtime.models import (
    LiveCredentialInjectionResult,
)


def __getattr__(name: str):
    if name == "LiveCredentialInjectionRuntime":
        from zeus_agent.live_credential_injection_runtime.runtime import LiveCredentialInjectionRuntime

        return LiveCredentialInjectionRuntime
    raise AttributeError(name)


__all__ = [
    "LiveCredentialInjectionResult",
    "LiveCredentialInjectionRuntime",
]
