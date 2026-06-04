from __future__ import annotations

from zeus_agent.live_agent_loop import controlled_fake_provider_turns


def test_controlled_fake_provider_streams_chunks_and_tool_call_without_network() -> None:
    first, final = controlled_fake_provider_turns("inspect local state")

    assert first.decision == "selected"
    assert first.tool_calls[0].tool_name == "local.echo"
    assert len(first.content.split("|")) >= 2
    assert first.network_opened is False
    assert final.tool_results[0].call_id == first.tool_calls[0].call_id
    assert final.network_opened is False
