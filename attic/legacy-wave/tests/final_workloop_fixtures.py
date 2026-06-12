from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from zeus_agent.verification_runtime import VerificationObligation
    from zeus_agent.workloop_runtime import OrchestrationLane


@dataclass(frozen=True)
class CompiledObjectiveFixture:
    goal_contract_id: str
    normalized_goal: str
    deliverables: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]


def objective_contract() -> CompiledObjectiveFixture:
    return CompiledObjectiveFixture(
        goal_contract_id="goal-final-workloop",
        normalized_goal="build persistent work loop and verification engine",
        deliverables=("work loop plan", "verification summary"),
        acceptance_criteria=(
            "REQ-ZEUS-FINAL-002:S1",
            "REQ-ZEUS-FINAL-003:S1",
        ),
    )


def valid_lanes() -> list["OrchestrationLane"]:
    return [
        lane(
            "workloop-runtime",
            "src/zeus_agent/workloop_runtime/**",
            blocks=["verification-runtime"],
            stop_condition="work loop plan emitted with disjoint lanes",
            evidence_target="tests/test_final_workloop_verification.py::test_happy_work_loop_plan_and_verification_complete_with_five_obligations",
        ),
        lane(
            "verification-runtime",
            "src/zeus_agent/verification_runtime/**",
            depends_on=["workloop-runtime"],
            blocks=["completion-gate"],
            stop_condition="verification summary emitted",
            evidence_target="tests/test_final_workloop_verification.py::test_planned_only_evidence_blocks_completion",
        ),
        lane(
            "completion-gate",
            "src/zeus_agent/kernel/completion.py",
            depends_on=["verification-runtime"],
            stop_condition="completion_allowed is true only for passed obligations",
            evidence_target="tests/test_final_workloop_verification.py::test_failed_obligation_blocks_completion",
        ),
        lane(
            "manual-qa",
            "harness/evidence/artifacts/final-qa.log",
            depends_on=["verification-runtime"],
            stop_condition="script PTY transcript captured by orchestrator",
            evidence_target="main-orchestrator-script-pty",
        ),
    ]


def passed_obligations() -> list["VerificationObligation"]:
    return [
        obligation(
            "verify-workloop-lanes",
            "REQ-ZEUS-FINAL-002:S1",
            "workloop-runtime",
            obligation_type="requirement",
            evidence_target="tests/test_final_workloop_verification.py::test_happy_work_loop_plan_and_verification_complete_with_five_obligations",
            evidence_status="passed",
        ),
        obligation(
            "verify-lane-evidence-targets",
            "REQ-ZEUS-FINAL-002:S1",
            "workloop-runtime",
            obligation_type="gate",
            evidence_target="python3 -m pytest tests/test_final_workloop_verification.py -q",
            evidence_status="passed",
        ),
        obligation(
            "verify-runtime-obligations",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target="python3 -m compileall src/zeus_agent/verification_runtime",
            evidence_status="passed",
        ),
        obligation(
            "verify-manual-qa-channel",
            "REQ-ZEUS-FINAL-003:S1",
            "manual-qa",
            obligation_type="manual_qa",
            evidence_target="main-orchestrator-script-pty",
            evidence_status="passed",
        ),
        obligation(
            "verify-completion-gate",
            "REQ-ZEUS-FINAL-003:S1",
            "completion-gate",
            obligation_type="gate",
            evidence_target="tests/test_final_workloop_verification.py::test_failed_obligation_blocks_completion",
            evidence_status="passed",
        ),
    ]


def lane(
    lane_id: str,
    owned_path: str,
    *,
    depends_on: Sequence[str] = (),
    blocks: Sequence[str] = (),
    stop_condition: str,
    evidence_target: Optional[str],
) -> "OrchestrationLane":
    from zeus_agent.workloop_runtime import OrchestrationLane

    return OrchestrationLane(
        lane_id=lane_id,
        owned_paths=[owned_path],
        depends_on=list(depends_on),
        blocks=list(blocks),
        stop_condition=stop_condition,
        manual_qa_channel="script-pty",
        evidence_target=evidence_target,
    )


def obligation(
    obligation_id: str,
    requirement_id: str,
    lane_id: str,
    *,
    obligation_type: str,
    evidence_target: Optional[str],
    evidence_status: str,
    failure_reason: Optional[str] = None,
) -> "VerificationObligation":
    from zeus_agent.verification_runtime import VerificationObligation

    return VerificationObligation(
        obligation_id=obligation_id,
        requirement_id=requirement_id,
        lane_id=lane_id,
        obligation_type=obligation_type,
        evidence_target=evidence_target,
        evidence_status=evidence_status,
        failure_reason=failure_reason,
    )
