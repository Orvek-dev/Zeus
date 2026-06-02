from __future__ import annotations

from pathlib import Path

import pytest

from final_workloop_fixtures import (
    obligation,
    objective_contract,
    passed_obligations,
    valid_lanes,
)


def test_missing_passed_file_artifact_blocks_when_artifact_checking_is_required(
    tmp_path: Path,
) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    missing_targets = [
        ".omo/ulw-loop/evidence/does-not-exist.txt",
        "harness/evidence/artifacts/does-not-exist.log",
        "artifacts/final-output",
        str(tmp_path / "absolute-missing.json"),
    ]
    obligations = [
        *passed_obligations(),
        *[
            obligation(
                "verify-file-artifact-exists-{0}".format(index),
                "REQ-ZEUS-FINAL-003:S1",
                "verification-runtime",
                obligation_type="runtime",
                evidence_target=missing_target,
                evidence_status="passed",
            )
            for index, missing_target in enumerate(missing_targets, start=1)
        ],
    ]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        require_existing_artifacts=True,
        artifact_root=tmp_path,
    )

    assert summary.completion_allowed is False
    assert summary.blocked_obligation_ids == [
        "verify-file-artifact-exists-1",
        "verify-file-artifact-exists-2",
        "verify-file-artifact-exists-3",
        "verify-file-artifact-exists-4",
    ]
    assert summary.blocked_reasons == [
        "obligation:verify-file-artifact-exists-1:missing_evidence_artifact:"
        ".omo/ulw-loop/evidence/does-not-exist.txt",
        "obligation:verify-file-artifact-exists-2:missing_evidence_artifact:"
        "harness/evidence/artifacts/does-not-exist.log",
        "obligation:verify-file-artifact-exists-3:missing_evidence_artifact:"
        "artifacts/final-output",
        "obligation:verify-file-artifact-exists-4:missing_evidence_artifact:"
        "{0}".format(tmp_path / "absolute-missing.json"),
    ]
    assert summary.passed_obligation_ids == [
        "verify-workloop-lanes",
        "verify-lane-evidence-targets",
        "verify-runtime-obligations",
        "verify-manual-qa-channel",
        "verify-completion-gate",
    ]


def test_missing_passed_artifact_uses_cwd_when_root_is_not_supplied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    monkeypatch.chdir(tmp_path)
    obligations = [
        obligation(
            "verify-cwd-artifact",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target="harness/evidence/artifacts/does-not-exist.log",
            evidence_status="passed",
        )
    ]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        required_obligation_ids=["verify-cwd-artifact"],
        require_existing_artifacts=True,
    )

    assert summary.completion_allowed is False
    assert summary.blocked_reasons == [
        "obligation:verify-cwd-artifact:missing_evidence_artifact:"
        "harness/evidence/artifacts/does-not-exist.log"
    ]


def test_passed_obligation_without_evidence_target_still_blocks_with_artifact_checking(
    tmp_path: Path,
) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    obligations = [
        obligation(
            "verify-target-present",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target=None,
            evidence_status="passed",
        )
    ]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        required_obligation_ids=["verify-target-present"],
        require_existing_artifacts=True,
        artifact_root=tmp_path,
    )

    assert summary.completion_allowed is False
    assert summary.blocked_reasons == ["obligation:verify-target-present:missing_evidence_target"]


def test_existing_fragment_artifact_passes_when_artifact_checking_is_required(
    tmp_path: Path,
) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    artifact_path = tmp_path / "harness" / "evidence" / "artifacts" / "present.log"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("manual QA transcript captured\n", encoding="utf-8")
    obligations = [
        obligation(
            "verify-fragment-artifact",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target="harness/evidence/artifacts/present.log#manual-qa",
            evidence_status="passed",
        )
    ]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        required_obligation_ids=["verify-fragment-artifact"],
        require_existing_artifacts=True,
        artifact_root=tmp_path,
    )

    assert summary.completion_allowed is True
    assert summary.blocked_reasons == []
    assert summary.passed_obligation_ids == ["verify-fragment-artifact"]


def test_missing_required_artifact_marker_blocks_completion(tmp_path: Path) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    artifact_path = tmp_path / "harness" / "evidence" / "artifacts" / "present.log"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("objective_compiled=true\n", encoding="utf-8")
    obligations = [
        obligation(
            "verify-marker",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target="harness/evidence/artifacts/present.log",
            evidence_status="passed",
        )
    ]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        required_obligation_ids=["verify-marker"],
        require_existing_artifacts=True,
        artifact_root=tmp_path,
        required_artifact_markers={
            "verify-marker": ("objective_compiled=true", "__QA_DONE__=0")
        },
    )

    assert summary.completion_allowed is False
    assert summary.blocked_reasons == [
        "obligation:verify-marker:missing_evidence_marker:__QA_DONE__=0"
    ]


def test_logical_targets_remain_approved_when_artifact_checking_is_required(
    tmp_path: Path,
) -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    obligations = passed_obligations()
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        require_existing_artifacts=True,
        artifact_root=tmp_path,
    )

    assert summary.completion_allowed is True
    assert summary.blocked_reasons == []
    assert summary.passed_obligation_ids == [
        "verify-workloop-lanes",
        "verify-lane-evidence-targets",
        "verify-runtime-obligations",
        "verify-manual-qa-channel",
        "verify-completion-gate",
    ]
