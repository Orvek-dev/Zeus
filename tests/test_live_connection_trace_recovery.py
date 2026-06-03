from __future__ import annotations

import json

import pytest

from zeus_agent.live_connection_runtime.recovery import (
    make_cleanup_obligation,
    make_cleanup_receipt,
    make_replay_request,
)
from zeus_agent.live_connection_runtime.trace import (
    append_trace_decision,
    serialized_has_no_secret_echo,
    start_live_connection_trace,
)


def test_trace_records_step_decision_history_without_side_effects_or_secret_echo() -> None:
    # Given: a trace that receives decision reasons containing secret-like spans.
    raw_sk_secret = "sk-live-trace-secret"
    raw_ghp_secret = "ghp_TRACE_FIXTURE"
    raw_private_key = (
        "-----BEGIN PRIVATE KEY-----abc123-----END PRIVATE KEY-----"
    )
    trace = start_live_connection_trace("trace.sk-live-trace-secret")

    # When: planning decisions are appended to the trace.
    planned = append_trace_decision(
        trace,
        step_id="step.provider.plan",
        decision="planned",
        reason=f"provider ready {raw_sk_secret}",
    )
    blocked = append_trace_decision(
        planned,
        step_id=f"step.gateway.{raw_ghp_secret}",
        decision="blocked",
        reason=f"gateway blocked private_key={raw_private_key}",
    )

    # Then: history and step IDs are retained with no handler or network claim.
    payload = blocked.model_dump(mode="json")
    serialized = blocked.model_dump_json()
    assert blocked.trace_id == "trace.[redacted-secret]"
    assert blocked.step_ids == ("step.provider.plan", "step.gateway.[redacted-secret]")
    assert [item["decision"] for item in payload["history"]] == [
        "planned",
        "blocked",
    ]
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_sk_secret not in serialized
    assert raw_ghp_secret not in serialized
    assert raw_private_key not in serialized
    assert serialized_has_no_secret_echo(serialized) is True


def test_replay_request_is_pure_and_references_existing_trace_step() -> None:
    # Given: a trace with a failed planning step.
    raw_secret = "sk-replay-secret"
    trace = append_trace_decision(
        start_live_connection_trace("trace.replay"),
        step_id="step.mcp.plan",
        decision="blocked",
        reason=f"mcp blocked {raw_secret}",
    )

    # When: a replay request is created for the known step.
    replay = make_replay_request(
        trace,
        replay_id=f"replay.{raw_secret}",
        from_step_id="step.mcp.plan",
        reason="operator requested replay after credential rotation",
    )

    # Then: the request is plan-only, side-effect-free, and JSON safe.
    serialized = json.dumps(replay.model_dump(mode="json"), sort_keys=True)
    assert replay.trace_id == "trace.replay"
    assert replay.from_step_id == "step.mcp.plan"
    assert replay.dry_run is True
    assert replay.handler_executed is False
    assert replay.network_opened is False
    assert replay.no_secret_echo is True
    assert raw_secret not in serialized
    assert serialized_has_no_secret_echo(serialized) is True


def test_replay_request_rejects_unknown_step_without_echoing_step_value() -> None:
    # Given: a trace with a single known step and an unknown secret-like step id.
    raw_step = "step.ghp_UNKNOWN_FIXTURE"
    trace = append_trace_decision(
        start_live_connection_trace("trace.replay.unknown"),
        step_id="step.provider.plan",
        decision="planned",
        reason="provider plan only",
    )

    # When / Then: unknown replay targets fail closed without echoing the input.
    with pytest.raises(ValueError) as raised:
        make_replay_request(
            trace,
            replay_id="replay.unknown",
            from_step_id=raw_step,
            reason="retry requested",
        )
    assert str(raised.value) == "unknown_trace_step"
    assert raw_step not in str(raised.value)


def test_cleanup_obligation_and_receipt_are_plan_only_and_secret_safe() -> None:
    # Given: a trace step that creates a cleanup obligation.
    raw_secret = "sk-cleanup-secret"
    trace = append_trace_decision(
        start_live_connection_trace("trace.cleanup"),
        step_id="step.gateway.plan",
        decision="cleanup_required",
        reason=f"rollback private-key={raw_secret}",
    )

    # When: cleanup obligation and receipt primitives are created.
    obligation = make_cleanup_obligation(
        trace,
        obligation_id=f"cleanup.{raw_secret}",
        step_id="step.gateway.plan",
        reason="remove staged gateway route",
    )
    receipt = make_cleanup_receipt(
        obligation,
        receipt_id="receipt.ghp_CLEANUP_FIXTURE",
        decision="completed",
        reason="cleanup confirmed without handler execution",
    )

    # Then: both primitives preserve planning state without execution or secret echo.
    serialized = json.dumps(
        {
            "obligation": obligation.model_dump(mode="json"),
            "receipt": receipt.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    assert obligation.trace_id == "trace.cleanup"
    assert obligation.step_id == "step.gateway.plan"
    assert obligation.required is True
    assert obligation.handler_executed is False
    assert obligation.network_opened is False
    assert receipt.obligation_id == "cleanup.[redacted-secret]"
    assert receipt.cleanup_decision == "completed"
    assert receipt.handler_executed is False
    assert receipt.network_opened is False
    assert raw_secret not in serialized
    assert "ghp_CLEANUP_FIXTURE" not in serialized
    assert serialized_has_no_secret_echo(serialized) is True


def test_trace_recovery_cleanup_redacts_private_key_with_spaced_separator() -> None:
    # Given: trace/recovery/cleanup inputs include private key markers with spaces.
    raw_trace_secret = "private_key = abc123"
    raw_cleanup_secret = "private-key : abc123"
    raw_named_secret = "private key:abc123"
    raw_lowercase_pem = (
        "-----begin private key-----abc123-----end private key-----"
    )
    trace = append_trace_decision(
        start_live_connection_trace(f"trace.{raw_named_secret}"),
        step_id="step.private-key : abc123",
        decision="cleanup_required",
        reason=f"rollback {raw_trace_secret} {raw_lowercase_pem}",
    )

    # When: recovery and cleanup records serialize their text fields.
    replay = make_replay_request(
        trace,
        replay_id="replay.private_key = abc123",
        from_step_id="step.[redacted-secret]",
        reason=f"retry {raw_trace_secret} {raw_named_secret}",
    )
    obligation = make_cleanup_obligation(
        trace,
        obligation_id="cleanup.private-key : abc123",
        step_id="step.[redacted-secret]",
        reason=f"cleanup {raw_cleanup_secret}",
    )
    receipt = make_cleanup_receipt(
        obligation,
        receipt_id="receipt.private_key = abc123",
        decision="completed",
        reason=f"done {raw_cleanup_secret}",
    )

    # Then: raw private-key-shaped values are absent and the echo detector agrees.
    serialized = json.dumps(
        {
            "trace": trace.model_dump(mode="json"),
            "replay": replay.model_dump(mode="json"),
            "obligation": obligation.model_dump(mode="json"),
            "receipt": receipt.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    assert raw_trace_secret not in serialized
    assert raw_cleanup_secret not in serialized
    assert raw_named_secret not in serialized
    assert raw_lowercase_pem not in serialized
    assert serialized_has_no_secret_echo(serialized) is True
