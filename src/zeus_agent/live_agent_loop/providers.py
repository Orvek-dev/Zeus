from __future__ import annotations

from zeus_agent.agent_runtime.live_loop_support import (
    provider_request,
    scripted_final_turn,
    scripted_tool_turn,
)
from zeus_agent.model_runtime.fake_provider import FakeProviderRuntime
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult


def controlled_fake_provider_turns(message: str):
    request = provider_request(message, stream=True)
    seed = FakeProviderRuntime().generate(
        request,
        RuntimeLeaseIntakeResult(
            decision="allowed",
            reason="runtime_lease_allowed",
            runtime_kind="provider",
            capability_id="provider.fake.generate",
            evidence_target="mneme.wave15.live_agent",
        ),
    )
    first = scripted_tool_turn(seed, message, "local.echo")
    final = scripted_final_turn(seed, first.tool_calls[0].call_id)
    return first, final


__all__ = ["controlled_fake_provider_turns"]
