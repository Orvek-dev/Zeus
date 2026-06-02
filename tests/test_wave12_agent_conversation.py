from __future__ import annotations

from pathlib import Path

from zeus_agent.agent_runtime.conversation import Wave12ConversationRuntime
from zeus_agent.wave12_conversation_scenarios import (
    wave12_conversation_blocks_payload,
    wave12_conversation_happy_payload,
)


def test_wave12_runtime_orchestrates_provider_tool_lineage_and_verification(
    tmp_path: Path,
) -> None:
    # Given: a dry-run Wave12 conversation runtime and an isolated state home.
    runtime = Wave12ConversationRuntime(home=tmp_path)

    # When: a user message asks the runtime to inspect, call echo, and summarize.
    payload = runtime.run_turn(
        message="Inspect repo, call echo tool, summarize evidence",
    )

    # Then: Zeus policy absorbs the Hermes-style chat turn without live side effects.
    assert payload["scenario_id"] == "C001"
    assert payload["conversation_runtime_created"] is True
    assert payload["provider_invoked"] is True
    assert payload["tool_schema_compiled"] is True
    assert payload["tool_call_planned"] is True
    assert payload["broker_dispatch_allowed"] is True
    assert payload["tool_result_recorded"] is True
    assert payload["session_lineage_recorded"] is True
    assert payload["context_compressed"] is False
    assert payload["verification_completion_allowed"] is True
    assert payload["handler_executed"] is True
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_wave12_scenario_payloads_match_success_criteria(tmp_path: Path) -> None:
    # Given: Wave12 happy and blocked scenario payload builders.
    happy = wave12_conversation_happy_payload(
        message="Inspect repo, call echo tool, summarize evidence",
        home=tmp_path / "happy",
    )
    blocked = wave12_conversation_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )

    # When: their observable fields are evaluated against C001 and C002.
    required_happy = (
        "conversation_runtime_created",
        "provider_invoked",
        "tool_schema_compiled",
        "tool_call_planned",
        "broker_dispatch_allowed",
        "tool_result_recorded",
        "session_lineage_recorded",
        "verification_completion_allowed",
        "handler_executed",
        "no_secret_echo",
    )

    # Then: happy criteria pass and unsafe edge cases fail closed.
    assert all(happy[field] is True for field in required_happy)
    assert happy["context_compressed"] is False
    assert happy["network_opened"] is False
    assert blocked["empty_message"] == "blocked"
    assert blocked["malformed_tool_call"] == "blocked"
    assert blocked["missing_runtime_lease"] == "blocked"
    assert blocked["provider_fallback_recorded"] is True
    assert blocked["retry_limit_enforced"] is True
    assert blocked["unsafe_context_injection"] == "blocked"
    assert blocked["unknown_tool"] == "blocked"
    assert blocked["completion_gate_blocks_missing_evidence"] is True
    assert blocked["handler_executed"] is False
    assert blocked["network_opened"] is False
    assert blocked["raw_secret_present"] is False


def test_wave12_blocks_payload_uses_real_empty_message_runtime(monkeypatch) -> None:
    # Given: the block payload builder and a runtime spy for blank turns.
    original = Wave12ConversationRuntime.run_turn
    observed_messages: list[str] = []

    def spy_run_turn(self: Wave12ConversationRuntime, message: str) -> dict[str, object]:
        observed_messages.append(message)
        return original(self, message)

    monkeypatch.setattr(Wave12ConversationRuntime, "run_turn", spy_run_turn)

    # When: the C002 block payload is built.
    payload = wave12_conversation_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )

    # Then: empty-message evidence is produced by the real runtime path.
    assert payload["empty_message"] == "blocked"
    assert observed_messages == ["   "]
