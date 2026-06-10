from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.goal_intelligence_runtime.intent import IntentFrame
from zeus_agent.objective_frame_runtime import (
    intent_seed,
    parse_frame,
    produce_frame,
    provider_generate,
)
from zeus_agent.provider_capability_runtime import CanonicalProviderHandler, ProviderVendor
from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger

runner = CliRunner()

_VALID_FRAME = {
    "normalized_objective": "Summarize a document",
    "triage": "oneshot",
    "required_criteria": ["summary"],
    "candidates": [
        {
            "candidate_id": "summarize",
            "nodes": [
                {"node_id": "read", "kind": "llm_generic", "produces_criteria": ["summary"]},
                {"node_id": "check", "kind": "verification", "verifies_criteria": ["summary"]},
            ],
            "edges": [{"src": "read", "dst": "check"}],
        }
    ],
}


# --- Deterministic parse (the Zeus-owned half) ------------------------------


def test_parse_valid_frame() -> None:
    result = parse_frame(json.dumps(_VALID_FRAME))
    assert result.ok is True
    assert result.frame is not None
    assert result.frame.normalized_objective == "Summarize a document"


def test_parse_malformed_json_blocks() -> None:
    result = parse_frame("{not json")
    assert result.decision == "blocked"
    assert result.blocked_reason == "malformed_frame_json"


def test_parse_schema_violation_blocks() -> None:
    result = parse_frame(json.dumps({"triage": "nonsense"}))
    assert result.decision == "blocked"
    assert result.blocked_reason == "malformed_objective_frame"


def test_parse_secret_bearing_output_blocks_and_scrubs() -> None:
    poisoned = json.dumps({**_VALID_FRAME, "normalized_objective": "use sk-proj-THISISSECRET"})
    result = parse_frame(poisoned)
    assert result.decision == "blocked"
    assert result.blocked_reason == "raw_secret_in_frame"
    assert "THISISSECRET" not in str(result.model_dump())


# --- The LLM seam (injectable, deterministic) -------------------------------


def test_produce_frame_with_injected_generate() -> None:
    result = produce_frame(utterance="summarize my doc", generate=lambda _p: json.dumps(_VALID_FRAME))
    assert result.ok is True
    assert result.frame.normalized_objective == "Summarize a document"


def test_produce_frame_rejects_secret_utterance() -> None:
    result = produce_frame(utterance="my key sk-proj-THISISSECRET", generate=lambda _p: "{}")
    assert result.decision == "blocked"
    assert result.blocked_reason == "raw_secret_in_utterance"


def test_produce_frame_empty_utterance_blocks() -> None:
    result = produce_frame(utterance="   ", generate=lambda _p: json.dumps(_VALID_FRAME))
    assert result.decision == "blocked"
    assert result.blocked_reason == "empty_utterance"


def test_provider_backed_fake_vendor_fails_closed(tmp_path) -> None:
    # The fake vendor returns plain text, not a JSON frame → fail closed, not crash.
    handler = CanonicalProviderHandler(ledger=SQLiteEvidenceLedger(tmp_path / "ev.sqlite3"))
    gen = provider_generate(handler, vendor=ProviderVendor.fake, model_id="fake.model")
    result = produce_frame(utterance="do a thing", generate=gen)
    assert result.decision == "blocked"
    assert result.blocked_reason == "malformed_frame_json"


# --- IntentFrame bridge is a SEED, not a 1:1 map ----------------------------


def test_intent_seed_is_a_hint_not_a_frame() -> None:
    frame = IntentFrame(
        desired_outcome="ship a feature",
        acceptance_criteria=("tests pass",),
        unknowns=("acceptance_criteria",),
        confidence=0.6,
    )
    seed = intent_seed(frame)
    assert "desired_outcome: ship a feature" in seed
    assert "open_meta_gaps: acceptance_criteria" in seed


# --- CLI front door ---------------------------------------------------------


def test_cli_objective_compiles_injected_frame() -> None:
    result = runner.invoke(
        app,
        ["objective", "--utterance", "summarize my doc", "--frame-output", json.dumps(_VALID_FRAME), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["chosen_workflow_id"] == "summarize"
    assert payload["decision"] == "ready_to_start"


def test_cli_objective_without_provider_is_honest() -> None:
    result = runner.invoke(app, ["objective", "--utterance", "do something", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked"
    assert payload["blocked_reasons"] == ["empty_frame_output"]
