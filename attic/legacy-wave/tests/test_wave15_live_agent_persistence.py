from __future__ import annotations

import sqlite3

from zeus_agent.wave15_live_agent_scenarios import wave15_live_agent_blocks_payload


def test_live_agent_denied_paths_persist_redacted_audit_without_side_effects(tmp_path) -> None:
    raw_secret = "sk-wave15-deny-secret"
    home = tmp_path / "wave15-deny"

    payload = wave15_live_agent_blocks_payload(home=home, raw_secret=raw_secret)

    assert payload["audit_events"] >= 6
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    with sqlite3.connect(home / "wave15-state.sqlite3") as connection:
        summaries = [row[0] for row in connection.execute("SELECT summary FROM audit_log_events")]
    serialized = "\n".join(summaries)
    assert "wave15.live_agent.deny" in serialized
    assert "retry_limit_enforced" in serialized
    assert "fallback_route_recorded" in serialized
    assert "cancellation_recorded" in serialized
    assert raw_secret not in serialized
