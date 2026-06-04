from __future__ import annotations

from typing import TYPE_CHECKING, Union

from .models import LiveAgentLoopRequest, LiveAgentLoopResult, RetryPolicy
from .providers import controlled_fake_provider_turns
from .tools import build_local_echo_tool_runtime

if TYPE_CHECKING:
    from .runtime import LiveAgentLoop
    from .store import LiveAgentLoopPersistence

__all__ = [
    "LiveAgentLoop",
    "LiveAgentLoopPersistence",
    "LiveAgentLoopRequest",
    "LiveAgentLoopResult",
    "RetryPolicy",
    "build_local_echo_tool_runtime",
    "controlled_fake_provider_turns",
]


def __getattr__(
    name: str,
) -> Union[type["LiveAgentLoop"], type["LiveAgentLoopPersistence"]]:
    if name == "LiveAgentLoop":
        from .runtime import LiveAgentLoop

        return LiveAgentLoop
    if name == "LiveAgentLoopPersistence":
        from .store import LiveAgentLoopPersistence

        return LiveAgentLoopPersistence
    raise AttributeError(name)
