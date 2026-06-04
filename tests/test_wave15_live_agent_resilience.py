from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.agent_runtime.live_loop import LiveAgentLoop
from zeus_agent.agent_runtime.live_loop_models import RetryPolicy
from zeus_agent.agent_runtime.live_loop_support import MAX_ECHO_TEXT_LENGTH
from wave15_live_agent_test_support import (
    BlockingProviderRegistry,
    FallbackProviderRegistry,
    FinalBlockedNetworkProviderRegistry,
    FinalTransientProviderRegistry,
    audit_summaries,
    tool_call_count,
)


def test_wave15_retry_exhaustion_repeats_provider_attempts_and_persists_audit(
    tmp_path: Path,
) -> None:
    # Given: a provider surface that keeps failing under an explicit retry limit.
    provider = BlockingProviderRegistry()
    runtime = LiveAgentLoop(home=tmp_path / "wave15-retry", provider_registry=provider)

    # When: the live loop runs with retry policy exhaustion.
    result = runtime.run_tool_loop(
        message="retry the local provider until exhausted",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        retry_policy=RetryPolicy(max_attempts=3),
    )

    # Then: the provider was actually attempted three times and only then audited.
    assert len(provider.requests) == 3
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("retry_limit_enforced",)
    assert result.provider_turns == 3
    assert result.handler_executed is False
    assert result.network_opened is False
    serialized = json.dumps(
        audit_summaries(tmp_path / "wave15-retry" / "wave15-state.sqlite3"),
        sort_keys=True,
    )
    assert "retry_limit_enforced" in serialized
    assert "attempts=3" in serialized


def test_wave15_cancellation_input_stops_before_provider_or_tool_side_effects(
    tmp_path: Path,
) -> None:
    # Given: a provider surface that would record an invocation if reached.
    provider = BlockingProviderRegistry()
    home = tmp_path / "wave15-cancel"
    runtime = LiveAgentLoop(home=home, provider_registry=provider)

    # When: cancellation is supplied as runtime state before dispatch.
    result = runtime.run_tool_loop(
        message="cancel before provider dispatch",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        cancellation_requested=True,
    )

    # Then: neither provider nor tool handler side effects occur and audit persists.
    assert provider.requests == []
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("cancellation_recorded",)
    assert result.provider_turns == 0
    assert result.handler_executed is False
    assert result.network_opened is False
    assert tool_call_count(home / "wave15-state.sqlite3") == 0
    assert "cancellation_recorded" in json.dumps(
        audit_summaries(home / "wave15-state.sqlite3"),
        sort_keys=True,
    )


def test_wave15_oversized_message_blocks_before_provider_or_tool_side_effects(
    tmp_path: Path,
) -> None:
    # Given: an authorized loop receives a message larger than local echo can store.
    provider = BlockingProviderRegistry()
    home = tmp_path / "wave15-large-message"
    runtime = LiveAgentLoop(home=home, provider_registry=provider)

    # When: the runtime evaluates the oversized message.
    result = runtime.run_tool_loop(
        message="x" * (MAX_ECHO_TEXT_LENGTH + 1),
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
    )

    # Then: it blocks before provider/tool side effects and audits only the size.
    assert provider.requests == []
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("message_too_large",)
    assert result.provider_turns == 0
    assert result.handler_executed is False
    assert result.network_opened is False
    serialized = json.dumps(audit_summaries(home / "wave15-state.sqlite3"), sort_keys=True)
    assert "message_too_large" in serialized
    assert "len=4097" in serialized


def test_wave15_fallback_executes_from_runtime_entry_point_and_persists_audit(
    tmp_path: Path,
) -> None:
    # Given: a primary provider failure followed by a local fallback provider.
    provider = FallbackProviderRegistry()
    home = tmp_path / "wave15-fallback"
    runtime = LiveAgentLoop(home=home, provider_registry=provider)

    # When: the live loop is allowed to select a fake/local fallback route.
    result = runtime.run_tool_loop(
        message="use fallback for local provider failure",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        fallback_provider_kind="local_llm",
    )

    # Then: fallback provider selection executed through the runtime and was audited.
    assert [request.provider_kind for request in provider.requests] == ["fake", "local_llm", "local_llm"]
    assert result.decision == "selected"
    assert result.provider_decision == "selected"
    assert result.provider_turns == 3
    assert result.handler_executed is True
    assert result.network_opened is False
    serialized = json.dumps(audit_summaries(home / "wave15-state.sqlite3"), sort_keys=True)
    assert "fallback_route_recorded" in serialized
    assert "fake->local_llm:selected" in serialized


def test_wave15_fallback_completion_uses_selected_fallback_lease_with_real_registry(
    tmp_path: Path,
) -> None:
    # Given: the primary provider lacks a lease, but a fake fallback has a valid lease.
    home = tmp_path / "wave15-real-fallback"
    runtime = LiveAgentLoop(home=home)

    # When: the normal local echo loop completes after selecting the fallback route.
    result = runtime.run_tool_loop(
        message="complete the live loop through the fallback provider",
        provider_lease=None,
        tool_lease=runtime.tool_lease(),
        fallback_provider_kind="fake",
        fallback_provider_lease=runtime.provider_lease(),
    )

    # Then: fallback remains selected for the final provider turn and session persistence.
    assert result.decision == "selected"
    assert result.provider_decision == "selected"
    assert result.provider_turns == 3
    assert result.tool_result_recorded is True
    assert result.handler_executed is True
    assert result.session_persisted is True
    assert tool_call_count(home / "wave15-state.sqlite3") == 1
    serialized = json.dumps(audit_summaries(home / "wave15-state.sqlite3"), sort_keys=True)
    assert "fallback_route_recorded" in serialized
    assert "fake->fake:selected" in serialized


def test_wave15_final_provider_turn_uses_retry_policy_before_blocking(tmp_path: Path) -> None:
    # Given: the initial provider turn succeeds, final turn blocks once, then recovers.
    provider = FinalTransientProviderRegistry()
    runtime = LiveAgentLoop(home=tmp_path / "wave15-final-retry", provider_registry=provider)

    # When: the loop has a retry policy covering provider execution.
    result = runtime.run_tool_loop(
        message="retry final provider turn after local tool",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        retry_policy=RetryPolicy(max_attempts=3),
    )

    # Then: the final provider turn is retried and the loop completes.
    assert [request.provider_kind for request in provider.requests] == ["fake", "fake", "fake"]
    assert result.decision == "selected"
    assert result.provider_turns == 3
    assert result.handler_executed is True
    assert result.session_persisted is True


def test_wave15_retry_policy_is_capped_for_provider_attempts(tmp_path: Path) -> None:
    # Given: an excessive retry request against a provider that always fails.
    provider = BlockingProviderRegistry()
    home = tmp_path / "wave15-retry-cap"
    runtime = LiveAgentLoop(home=home, provider_registry=provider)

    # When: the loop receives more requested attempts than the runtime cap allows.
    result = runtime.run_tool_loop(
        message="do not spin forever on provider errors",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        retry_policy=RetryPolicy(max_attempts=99),
    )

    # Then: provider attempts are clamped and the deny audit records the capped count.
    assert len(provider.requests) == 3
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("retry_limit_enforced",)
    assert result.provider_turns == 3
    assert "attempts=3" in json.dumps(
        audit_summaries(home / "wave15-state.sqlite3"),
        sort_keys=True,
    )


def test_wave15_final_provider_block_preserves_prior_side_effects(
    tmp_path: Path,
) -> None:
    # Given: a first provider turn marked as network-opened before a final block.
    provider = FinalBlockedNetworkProviderRegistry()
    runtime = LiveAgentLoop(home=tmp_path / "wave15-final-block", provider_registry=provider)

    # When: the final provider call blocks after the tool handler returns.
    result = runtime.run_tool_loop(
        message="final provider block after local tool",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
    )

    # Then: the blocked result preserves earlier handler and network side effects.
    assert result.decision == "blocked"
    assert result.provider_turns == 2
    assert result.handler_executed is True
    assert result.network_opened is True
    summaries = audit_summaries(tmp_path / "wave15-final-block" / "wave15-state.sqlite3")
    assert any(json.loads(summary)["handler_executed"] is True for summary in summaries)


def test_wave15_failed_fallback_after_retry_exhaustion_records_runtime_audit(
    tmp_path: Path,
) -> None:
    # Given: retry exhaustion followed by a fallback provider that also blocks.
    provider = BlockingProviderRegistry()
    home = tmp_path / "wave15-fallback-block"
    runtime = LiveAgentLoop(home=home, provider_registry=provider)

    # When: retry and fallback are both requested through the runtime entry point.
    result = runtime.run_tool_loop(
        message="retry then fallback but both providers fail",
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
        retry_policy=RetryPolicy(max_attempts=2),
        fallback_provider_kind="local_llm",
    )

    # Then: attempts include primary retries plus fallback, and both audits persist.
    assert len(provider.requests) == 3
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("retry_limit_enforced",)
    assert result.provider_turns == 3
    serialized = json.dumps(audit_summaries(home / "wave15-state.sqlite3"), sort_keys=True)
    assert "fallback_route_blocked" in serialized
    assert "fake->local_llm:blocked" in serialized
    assert "attempts=3" in serialized
