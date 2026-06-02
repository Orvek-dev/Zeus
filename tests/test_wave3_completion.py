from __future__ import annotations

from zeus_agent.kernel.completion import summarize_completion
from zeus_agent.kernel.contracts import GoalContract
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord


def test_summarize_completion_requires_pass_evidence_for_every_acceptance_criterion() -> None:
    # Given: a contract with two required acceptance criteria and PASS evidence for both.
    contract = _contract(["REQ-ZEUS-WAVE3-001:S1", "REQ-ZEUS-WAVE3-001:S2"])
    records = [
        _record("REQ-ZEUS-WAVE3-001:S1", EvidenceStatus.PASS),
        _record("REQ-ZEUS-WAVE3-001:S2", EvidenceStatus.PASS),
    ]

    # When: hardened completion is summarized from evidence.
    summary = summarize_completion(contract, records, final_message="done")

    # Then: the status is complete only because all requested criteria have PASS records.
    assert summary.status == "complete"
    assert summary.verified_criteria == [
        "REQ-ZEUS-WAVE3-001:S1",
        "REQ-ZEUS-WAVE3-001:S2",
    ]
    assert summary.missing_criteria == []


def test_summarize_completion_ignores_done_text_without_verified_evidence() -> None:
    # Given: the final assistant text claims completion but no evidence verifies the REQ.
    contract = _contract(["REQ-ZEUS-WAVE3-002:S1"])
    records: list[MnemeEvidenceRecord] = []

    # When: hardened completion is summarized from evidence and final prose.
    summary = summarize_completion(contract, records, final_message="done")

    # Then: model prose cannot complete the REQ and the missing ID is reported.
    assert summary.status == "blocked_missing_evidence"
    assert summary.verified_criteria == []
    assert summary.missing_criteria == ["REQ-ZEUS-WAVE3-002:S1"]


def test_summarize_completion_reports_blocked_policy_for_requested_blocked_evidence() -> None:
    # Given: a requested criterion has BLOCKED evidence from the execution path.
    contract = _contract(["REQ-ZEUS-WAVE3-003:S1"])
    records = [_record("REQ-ZEUS-WAVE3-003:S1", EvidenceStatus.BLOCKED)]

    # When: hardened completion is summarized from evidence.
    summary = summarize_completion(contract, records, final_message="complete")

    # Then: blocked evidence is treated as policy-blocked rather than complete.
    assert summary.status == "blocked_policy"
    assert summary.blocked_criteria == ["REQ-ZEUS-WAVE3-003:S1"]
    assert summary.verified_criteria == []
    assert summary.missing_criteria == []


def test_summarize_completion_ignores_evidence_from_another_goal_contract() -> None:
    # Given: a matching criterion has PASS evidence linked to another goal contract.
    contract = _contract(["REQ-ZEUS-WAVE3-004:S1"])
    records = [
        MnemeEvidenceRecord(
            run_id="run-wave3",
            goal_contract_id="other-goal",
            criterion_id="REQ-ZEUS-WAVE3-004:S1",
            evidence_type="completion_check",
            summary="unrelated evidence record",
            status=EvidenceStatus.PASS,
        )
    ]

    # When: hardened completion is summarized for the requested contract.
    summary = summarize_completion(contract, records, final_message="done")

    # Then: unrelated goal evidence cannot satisfy the requested REQ.
    assert summary.status == "blocked_missing_evidence"
    assert summary.verified_criteria == []
    assert summary.missing_criteria == ["REQ-ZEUS-WAVE3-004:S1"]


def test_summarize_completion_reports_failed_runtime_for_requested_fail_evidence() -> None:
    # Given: a requested criterion has FAIL evidence from runtime execution.
    contract = _contract(["REQ-ZEUS-WAVE3-005:S1"])
    records = [_record("REQ-ZEUS-WAVE3-005:S1", EvidenceStatus.FAIL)]

    # When: hardened completion is summarized from evidence.
    summary = summarize_completion(contract, records, final_message="done")

    # Then: runtime failure evidence is surfaced as failed_runtime.
    assert summary.status == "failed_runtime"
    assert summary.failed_criteria == ["REQ-ZEUS-WAVE3-005:S1"]
    assert summary.verified_criteria == []


def _contract(criteria: list[str]) -> GoalContract:
    return GoalContract(
        goal_contract_id="goal-wave3",
        raw_user_request="harden completion semantics",
        normalized_goal="summarize completion from evidence",
        deliverables=["completion summary"],
        acceptance_criteria=criteria,
    )


def _record(criterion_id: str, status: EvidenceStatus) -> MnemeEvidenceRecord:
    return MnemeEvidenceRecord(
        run_id="run-wave3",
        goal_contract_id="goal-wave3",
        criterion_id=criterion_id,
        evidence_type="completion_check",
        summary="evidence record",
        status=status,
    )
