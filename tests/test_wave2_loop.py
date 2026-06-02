from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zeus_agent.agent_runtime.prompt import build_prompt_context
from zeus_agent.cli import app
from zeus_agent.kernel.contracts import ExecutionMode, ExecutionSpec, GoalContract
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.state import SQLiteStateStore


def _run_wave2_loop(tmp_path: Path, scenario: str) -> dict[str, object]:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["wave2-loop", "--scenario", scenario, "--home", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0, result.stdout
    return json.loads(result.stdout)


def test_wave2_happy_loop_persists_session_model_turn_tool_call_evidence_and_acceptance_complete(
    tmp_path: Path,
) -> None:
    # Given: an isolated local Wave 2 home.
    # When: the happy fake loop runs through the CLI surface.
    payload = _run_wave2_loop(tmp_path, "happy")

    # Then: the user-facing JSON proves the loop persisted the linked domains.
    assert payload["session_id"] == "wave2-session-happy"
    assert payload["model_turn"]["turn_id"] == "turn-2-final"
    assert payload["tool_call"]["capability_id"] == "file.read"
    assert payload["broker_decision"]["decision"] == "allowed"
    assert payload["handler_executed"] is True
    assert payload["acceptance_evidence"] == {
        "status": "complete",
        "verified_criteria": ["REQ-ZEUS-WAVE2-001:S1"],
        "missing_criteria": [],
    }
    assert payload["state_counts"] == {
        "sessions": 1,
        "model_turns": 2,
        "tool_calls": 1,
        "evidence_records": 2,
        "acceptance_links": 1,
        "artifacts": 0,
        "connectors": 0,
        "workflows": 0,
        "ops_events": 0,
        "audit_events": 0,
    }

    state_db = Path(str(payload["state_db"]))
    with sqlite3.connect(state_db) as connection:
        rows = connection.execute(
            """
            SELECT s.session_id, t.turn_id, c.tool_call_id, e.criterion_id, l.status
            FROM session_state_sessions s
            JOIN session_state_model_turns t ON t.session_id = s.session_id
            JOIN session_state_tool_calls c ON c.turn_id = t.turn_id
            JOIN evidence_state_records e ON e.evidence_id = c.evidence_id
            JOIN evidence_state_acceptance_links l ON l.evidence_id = e.evidence_id
            WHERE s.session_id = ?
            """,
            (payload["session_id"],),
        ).fetchall()

    assert rows == [
        (
            "wave2-session-happy",
            "turn-1-tool",
            "tool-call-happy-1",
            "REQ-ZEUS-WAVE2-001:S1",
            "verified",
        )
    ]


def test_wave2_blocked_loop_rejects_unauthorized_tool_before_handler_with_blocked_evidence(
    tmp_path: Path,
) -> None:
    # Given: an isolated local Wave 2 home.
    # When: the fake model asks for a hidden mutating terminal tool.
    payload = _run_wave2_loop(tmp_path, "blocked")

    # Then: the broker blocks before the handler and persists blocked evidence.
    assert payload["session_id"] == "wave2-session-blocked"
    assert payload["tool_call"]["capability_id"] == "terminal.run"
    assert payload["broker_decision"]["decision"] == "blocked"
    assert payload["broker_decision"]["reason"] == "capability_not_model_visible"
    assert payload["handler_executed"] is False
    assert payload["acceptance_evidence"]["status"] == "blocked"
    assert payload["acceptance_evidence"]["missing_criteria"] == ["REQ-ZEUS-WAVE2-001:S1"]
    assert payload["state_counts"]["tool_calls"] == 1
    assert payload["state_counts"]["evidence_records"] == 2

    state_db = Path(str(payload["state_db"]))
    with sqlite3.connect(state_db) as connection:
        rows = connection.execute(
            """
            SELECT c.capability_id, c.broker_decision, c.handler_executed, e.status
            FROM session_state_tool_calls c
            JOIN evidence_state_records e ON e.evidence_id = c.evidence_id
            """
        ).fetchall()

    assert rows == [("terminal.run", "blocked", 0, "blocked")]


def test_wave2_prompt_context_includes_contract_run_visible_tools_but_hides_terminal_tool(
    tmp_path: Path,
) -> None:
    # Given: a happy fake loop with read-only authority.
    # When: the CLI returns the prompt context used for the model turn.
    payload = _run_wave2_loop(tmp_path, "happy")

    # Then: the prompt carries contract/run context and only model-visible tools.
    prompt_context = payload["prompt_context"]
    prompt_blob = json.dumps(prompt_context, sort_keys=True)
    assert "wave2-goal" in prompt_blob
    assert "wave2-run" in prompt_blob
    assert "REQ-ZEUS-WAVE2-001:S1" in prompt_blob
    assert prompt_context["visible_tools"] == ["file.read"]
    assert "terminal.run" not in prompt_blob
    assert "sk-test-secret" not in prompt_blob


def test_wave2_prompt_context_redacts_secret_like_contract_profile_and_tool_labels() -> None:
    # Given: real contract inputs carry a secret-like token across fields the prompt may emit.
    contract = GoalContract(
        goal_contract_id="goal-sk-test-secret",
        raw_user_request="raw request sk-test-secret",
        normalized_goal="persist evidence for sk-test-secret",
        deliverables=["deliverable sk-test-secret"],
        acceptance_criteria=["REQ-ZEUS-WAVE2-002:S1 sk-test-secret"],
    )
    execution = ExecutionSpec(
        run_id="run-sk-test-secret",
        goal_contract_id=contract.goal_contract_id,
        execution_mode=ExecutionMode.AUTHORIZED_DISPATCH,
    )

    # When: prompt context is built from the actual contract boundary.
    prompt_context = build_prompt_context(
        contract,
        execution,
        ["file.read:sk-test-secret"],
        "coding-agent sk-test-secret",
    )

    # Then: no prompt surface emits the original token.
    prompt_blob = json.dumps(prompt_context.model_dump(mode="json"), sort_keys=True)
    assert "sk-test-secret" not in prompt_blob
    assert "[REDACTED_SECRET]" in prompt_blob
    assert prompt_context.visible_tools == ["file.read:[REDACTED_SECRET]"]


def test_state_store_rejects_orphan_model_turn(tmp_path: Path) -> None:
    # Given: an empty state store with no session parent.
    store = SQLiteStateStore(tmp_path / "state.sqlite3")

    # When / Then: inserting a model turn for a missing session fails at the database boundary.
    with pytest.raises(sqlite3.IntegrityError):
        store.add_model_turn("turn-orphan", "missing-session", "assistant", "content")


def test_state_store_rejects_orphan_tool_call(tmp_path: Path) -> None:
    # Given: an evidence parent exists but the model turn parent does not.
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    store.add_evidence("evidence-1", _evidence_record())

    # When / Then: inserting a tool call for a missing turn fails at the database boundary.
    with pytest.raises(sqlite3.IntegrityError):
        store.add_tool_call(
            "tool-call-orphan",
            "missing-turn",
            "file.read",
            {"path": "/virtual/file.txt"},
            "allowed",
            True,
            "evidence-1",
        )


def test_state_store_rejects_orphan_acceptance_link(tmp_path: Path) -> None:
    # Given: an empty state store with no evidence parent.
    store = SQLiteStateStore(tmp_path / "state.sqlite3")

    # When / Then: inserting an acceptance link for missing evidence fails at the database boundary.
    with pytest.raises(sqlite3.IntegrityError):
        store.add_acceptance_link("REQ-ZEUS-WAVE2-002:S1", "missing-evidence", "verified")


def _evidence_record() -> MnemeEvidenceRecord:
    return MnemeEvidenceRecord(
        run_id="run-1",
        goal_contract_id="goal-1",
        criterion_id="REQ-ZEUS-WAVE2-002:S1",
        evidence_type="broker_decision",
        summary="test evidence",
        status=EvidenceStatus.PASS,
        capability_id="file.read",
    )
