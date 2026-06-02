from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.eval.final_architecture import run_final_architecture_eval
from zeus_agent.product_runtime import (
    SQLiteProductRuntimeStore,
    final_adversarial_blocks_payload,
    final_core_contracts_payload,
    final_state_persistence_payload,
)


def test_final_core_contracts_payload_links_product_runtime_layers(tmp_path) -> None:
    raw_secret = "ghp_TEST_FIXTURE"

    payload = final_core_contracts_payload(
        objective=(
            "Implement final Zeus architecture with Objective Compiler, Work Loop, "
            "Verification Engine, Promotion controls, and Skill Evolution."
        ),
        raw_secret=raw_secret,
        evidence_root=tmp_path,
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["objective_compiled"] is True
    assert payload["work_loop_plan_created"] is True
    assert payload["verification_obligations"] >= 5
    assert payload["verification_completion_allowed"] is False
    assert any(
        "missing_evidence_artifact" in reason for reason in payload["blocked_reasons"]
    )
    assert payload["promotion_live_transport"] is False
    assert payload["promotion_decision"] == "blocked"
    assert payload["promotion_reason"] == "live_transport_not_authorized"
    assert payload["skill_evolution_candidate_status"] == "proposed_not_promoted"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized


def test_final_adversarial_blocks_payload_fails_closed() -> None:
    raw_secret = "sk-final-adversarial-secret"

    payload = final_adversarial_blocks_payload(raw_secret=raw_secret)
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["boundary_empty_malformed_proof"] is True
    assert payload["empty_objective"] == "blocked"
    assert payload["malformed_constraint"] == "blocked"
    assert payload["prompt_injection"] == "flagged"
    assert payload["authority_widening"] == "blocked"
    assert payload["live_transport_not_authorized"] == "blocked"
    assert payload["unsafe_skill_auto_promotion"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized


def test_final_cli_core_and_adversarial_surfaces_emit_json() -> None:
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    core = runner.invoke(
        app,
        [
            "final-core",
            "--objective",
            "Implement final Zeus architecture with governed dry-run runtime.",
            "--secret-like",
            raw_secret,
            "--json",
        ],
    )
    adversarial = runner.invoke(
        app,
        ["final-adversarial", "--secret-like", raw_secret, "--json"],
    )

    assert core.exit_code == 0, core.stdout
    assert adversarial.exit_code == 0, adversarial.stdout
    assert json.loads(core.stdout)["objective_compiled"] is True
    assert json.loads(adversarial.stdout)["unsafe_skill_auto_promotion"] == "blocked"
    assert raw_secret not in core.stdout
    assert raw_secret not in adversarial.stdout


def test_final_product_state_persists_and_reloads_snapshot(tmp_path) -> None:
    raw_secret = "ghp_TEST_FIXTURE"

    payload = final_state_persistence_payload(home=tmp_path, raw_secret=raw_secret)

    assert payload["product_state_snapshot_count"] == 1
    assert payload["product_state_reload_stable"] is True
    assert payload["work_loop_state_work_loops"] == 1
    assert payload["work_loop_state_lane_steps"] >= 5
    assert payload["work_loop_state_completed_steps"] == 1
    assert payload["work_loop_state_reload_stable"] is True
    assert payload["verification_obligations"] >= 5
    assert payload["promotion_live_transport"] is False
    assert payload["skill_evolution_candidate_status"] == "proposed_not_promoted"
    assert payload["no_secret_echo"] is True
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_final_product_state_store_rejects_conflicting_replay(tmp_path) -> None:
    from zeus_agent.product_runtime import ProductRuntimeSnapshot
    from zeus_agent.state import IdempotencyConflictError

    first = ProductRuntimeSnapshot.model_validate(
        final_core_contracts_payload(
            objective="Implement final Zeus architecture with stable product state.",
            raw_secret="ghp_TEST_FIXTURE",
        ),
    )
    second = first.model_copy(update={"work_loop_id": "different-workloop"})
    store = SQLiteProductRuntimeStore(tmp_path / "state.sqlite3")

    store.add_snapshot(
        snapshot_id="snapshot",
        snapshot=first,
        idempotency_key="idem-snapshot",
    )

    try:
        store.add_snapshot(
            snapshot_id="snapshot",
            snapshot=second,
            idempotency_key="idem-snapshot",
        )
    except IdempotencyConflictError as exc:
        assert "product_runtime_snapshots" in str(exc)
    else:
        raise AssertionError("conflicting product runtime replay should fail closed")


def test_final_state_cli_reports_reload_stability(tmp_path) -> None:
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    result = runner.invoke(
        app,
        [
            "final-state",
            "--home",
            str(tmp_path),
            "--secret-like",
            raw_secret,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["product_state_snapshot_count"] == 1
    assert payload["product_state_reload_stable"] is True
    assert payload["work_loop_state_work_loops"] == 1
    assert payload["work_loop_state_reload_stable"] is True
    assert raw_secret not in result.stdout


def test_final_eval_cli_reports_adjacent_surface_compatibility() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["final-eval", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "final_architecture"
    assert payload["final_product_tests_passed"] is True
    assert payload["adjacent_surface_still_works"] is True
    assert payload["failed"] == 0


def test_final_architecture_eval_is_deterministic() -> None:
    first = run_final_architecture_eval()
    second = run_final_architecture_eval()

    assert first == second
    assert first["total"] >= 7
    assert first["passed"] == first["total"]
