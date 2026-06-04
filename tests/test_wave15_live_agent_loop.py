from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from zeus_agent.agent_runtime.live_loop import LiveAgentLoop
from zeus_agent.wave15_live_agent_scenarios import (
    wave15_live_agent_blocks_payload,
    wave15_live_agent_payload,
)


def test_wave15_live_agent_loop_processes_streaming_provider_tool_turns(
    tmp_path: Path,
) -> None:
    # Given: a fake/local Wave15 live agent scenario with isolated state.
    home = tmp_path / "wave15-live"

    # When: the runtime executes the scripted provider tool loop.
    payload = wave15_live_agent_payload(home=home, scenario="tool-loop")

    # Then: provider tool calls, evidence, session persistence, and verification pass.
    assert payload["live_agent_loop_created"] is True
    assert payload["provider_decision"] == "selected"
    assert payload["provider_turns"] >= 2
    assert payload["streaming_chunks_recorded"] is True
    assert payload["tool_calls_processed"] >= 1
    assert payload["tool_result_recorded"] is True
    assert payload["evidence_records"] >= 2
    assert payload["audit_events"] >= 1
    assert payload["audit_record_created"] is True
    assert payload["session_persisted"] is True
    assert payload["verification_completion_allowed"] is True
    assert payload["handler_executed"] is True
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_wave15_live_agent_loop_blocks_unsafe_cases_without_side_effects(
    tmp_path: Path,
) -> None:
    # Given: unsafe provider, tool, and context cases with a secret-like fixture.
    raw_secret = "sk-live-agent-fixture"

    # When: the block scenario is evaluated through the real runtime helpers.
    payload = wave15_live_agent_blocks_payload(
        home=tmp_path / "wave15-blocks",
        raw_secret=raw_secret,
    )

    # Then: every unsafe path fails closed without handler execution or secret echo.
    assert payload["empty_message"] == "blocked"
    assert payload["malformed_tool_call"] == "blocked"
    assert payload["missing_provider_lease"] == "blocked"
    assert payload["missing_tool_lease"] == "blocked"
    assert payload["unknown_tool"] == "blocked"
    assert payload["message_too_large"] == "blocked"
    assert payload["large_message_provider_attempts"] == 0
    assert payload["retry_limit_enforced"] is True
    assert payload["retry_provider_attempts"] == 2
    assert payload["cancellation_recorded"] is True
    assert payload["cancellation_provider_attempts"] == 0
    assert payload["fallback_route_recorded"] is True
    assert payload["fallback_completed"] is True
    assert payload["fallback_handler_executed"] is True
    assert payload["fallback_provider_attempts"] >= 3
    assert payload["unsafe_context_injection"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["audit_events"] >= 1
    assert payload["audit_record_created"] is True
    assert payload["raw_secret_present"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_wave15_live_agent_loop_persists_redacted_audit_for_allowed_local_dispatch(
    tmp_path: Path,
) -> None:
    # Given: an allowed fake/local dispatch with a secret-like safe message.
    raw_secret = "sk-wave15-audit-secret"
    home = tmp_path / "wave15-audit"
    runtime = LiveAgentLoop(home=home)

    # When: the live loop completes with provider and tool authority.
    result = runtime.run_tool_loop(
        message="inspect local state with token {0}".format(raw_secret),
        provider_lease=runtime.provider_lease(),
        tool_lease=runtime.tool_lease(),
    )

    # Then: a durable audit row is persisted and its summary is redacted.
    assert result.decision == "selected"
    assert result.audit_events >= 1
    assert result.audit_record_created is True
    summaries = _audit_summaries(home / "wave15-state.sqlite3")
    assert len(summaries) >= 1
    assert raw_secret not in json.dumps(summaries, sort_keys=True)
    assert "sk-...redacted" in json.dumps(summaries, sort_keys=True)


def test_wave15_runtime_missing_provider_lease_blocks_before_tool_handler(
    tmp_path: Path,
) -> None:
    # Given: the live loop runtime without provider lease authority.
    runtime = LiveAgentLoop(home=tmp_path / "wave15-provider-lease")

    # When: a valid message is run with no provider lease.
    result = runtime.run_tool_loop(
        message="inspect local state and call the evidence tool",
        provider_lease=None,
        tool_lease=runtime.tool_lease(),
    )

    # Then: provider authorization fails before any tool handler or network side effect.
    assert result.decision == "blocked"
    assert result.blocked_reasons == ("missing_provider_lease",)
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.audit_events >= 1
    assert result.audit_record_created is True
    summaries = _audit_summaries(tmp_path / "wave15-provider-lease" / "wave15-state.sqlite3")
    assert any("wave15.live_agent.deny" in summary for summary in summaries)


def _audit_summaries(db_path: Path) -> tuple[str, ...]:
    assert db_path.exists(), "expected audit database to exist"
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT summary FROM audit_log_events ORDER BY event_id").fetchall()
    return tuple(str(row[0]) for row in rows)
