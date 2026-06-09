from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.objective_run_runtime import ObjectiveRunRuntime, ObjectiveRunStore, ObjectiveRunStoreError


def test_objective_run_start_persists_contract_and_blocks_completion_without_evidence(tmp_path: Path) -> None:
    # Given: a fresh local Zeus home.
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(tmp_path))

    # When: an objective run is started from a natural-language goal.
    result = runtime.start(
        objective="Review this repository and produce an evidence-backed security issue draft.",
        session_id="session.v410",
        principal_id="operator.local",
    )

    # Then: Zeus creates a run spine without opening live execution.
    assert result.decision == "started"
    assert result.run.status == "planned"
    assert result.run.objective_contract.status == "compiled"
    assert result.run.goal_contract.goal_contract_id == result.run.objective_contract.objective_id
    assert result.run.completion_summary.status == "blocked_missing_evidence"
    assert result.run.network_opened is False
    assert result.run.handler_executed is False
    assert result.run.live_production_claimed is False

    stored = runtime.status(result.run.run_id)
    assert stored.decision == "reported"
    assert stored.run.run_id == result.run.run_id
    assert stored.run.completion_summary.status == "blocked_missing_evidence"


def test_objective_run_completion_turns_complete_only_after_criterion_evidence(tmp_path: Path) -> None:
    # Given: a started run with explicit acceptance criteria.
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(tmp_path))
    started = runtime.start(
        objective="Create an evidence-backed implementation plan.",
        acceptance_criteria=("contract-created", "evidence-exported"),
        session_id="session.v410",
        principal_id="operator.local",
    )

    # When: only one acceptance criterion has evidence.
    partial = runtime.record_evidence(
        run_id=started.run.run_id,
        evidence=MnemeEvidenceRecord(
            run_id=started.run.run_id,
            goal_contract_id=started.run.goal_contract.goal_contract_id,
            criterion_id="contract-created",
            evidence_type="objective_contract_created",
            summary="Objective contract was compiled.",
            status=EvidenceStatus.PASS,
        ),
    )

    # Then: Zeus still blocks completion because the other criterion is missing.
    assert partial.run.status == "verifying"
    assert partial.run.completion_summary.status == "blocked_missing_evidence"
    assert partial.run.completion_summary.verified_criteria == ["contract-created"]
    assert partial.run.completion_summary.missing_criteria == ["evidence-exported"]

    complete = runtime.record_evidence(
        run_id=started.run.run_id,
        evidence=MnemeEvidenceRecord(
            run_id=started.run.run_id,
            goal_contract_id=started.run.goal_contract.goal_contract_id,
            criterion_id="evidence-exported",
            evidence_type="run_export",
            summary="Run export contains evidence state.",
            status=EvidenceStatus.PASS,
        ),
    )

    assert complete.run.status == "complete"
    assert complete.run.completion_summary.status == "complete"
    assert complete.run.live_production_claimed is False


def test_cli_objective_start_status_and_export_share_run_store(tmp_path: Path) -> None:
    # Given: the Zeus CLI and an isolated local home.
    runner = CliRunner()

    # When: a user starts an objective run and then reads it back.
    started = runner.invoke(
        app,
        [
            "objective-start",
            "--objective",
            "제우스야, repo를 검토하고 evidence report를 만들어줘.",
            "--session-id",
            "session.cli",
            "--principal-id",
            "operator.local",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.stdout
    start_payload = json.loads(started.stdout)
    run_id = start_payload["run"]["run_id"]

    status = runner.invoke(
        app,
        ["objective-status", "--run-id", run_id, "--home", str(tmp_path), "--json"],
    )
    exported = runner.invoke(
        app,
        ["objective-export", "--run-id", run_id, "--home", str(tmp_path), "--json"],
    )

    # Then: all CLI surfaces report the same objective run spine.
    assert status.exit_code == 0, status.stdout
    assert exported.exit_code == 0, exported.stdout
    status_payload = json.loads(status.stdout)
    export_payload = json.loads(exported.stdout)
    assert status_payload["decision"] == "reported"
    assert status_payload["run"]["run_id"] == run_id
    assert status_payload["run"]["completion_summary"]["status"] == "blocked_missing_evidence"
    assert export_payload["decision"] == "exported"
    assert export_payload["run"]["run_id"] == run_id
    assert export_payload["run"]["handler_executed"] is False
    assert export_payload["run"]["live_production_claimed"] is False


def test_library_objective_start_status_and_export_share_run_store(tmp_path: Path) -> None:
    agent = ZeusAgent(home=tmp_path)

    started = agent.objective_start(
        objective="Zeus, turn this product goal into an evidence-backed run.",
        session_id="session.library",
        principal_id="operator.local",
        acceptance_criteria=("objective-run-created",),
    )
    run_id = started["run"]["run_id"]
    status = agent.objective_status(run_id=run_id)
    exported = agent.objective_export(run_id=run_id)

    assert started["decision"] == "started"
    assert status["decision"] == "reported"
    assert exported["decision"] == "exported"
    assert status["run"]["run_id"] == run_id
    assert exported["run"]["completion_summary"]["status"] == "blocked_missing_evidence"
    assert exported["run"]["handler_executed"] is False
    assert exported["run"]["live_production_claimed"] is False


def test_objective_run_store_fails_closed_when_store_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "objective-runs.json").write_text("{not valid json", encoding="utf-8")
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(tmp_path))

    try:
        runtime.start(
            objective="Create a governed objective run without overwriting corrupted history.",
            session_id="session.invalid-store",
            principal_id="operator.local",
        )
    except ObjectiveRunStoreError as exc:
        assert str(exc) == "objective_run_store_invalid"
    else:
        raise AssertionError("ObjectiveRunStoreError was not raised")
