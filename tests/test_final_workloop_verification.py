from __future__ import annotations

import importlib

from final_workloop_fixtures import lane, obligation, objective_contract, passed_obligations, valid_lanes


def test_final_architecture_runtime_packages_are_importable() -> None:
    # Given: Wave1-8 do not provide final work-loop or verification packages yet.
    # When: the final architecture runtime packages are imported.
    workloop = importlib.import_module("zeus_agent.workloop_runtime")
    verification = importlib.import_module("zeus_agent.verification_runtime")

    # Then: both packages expose product-level planning and verification types.
    assert hasattr(workloop, "WorkLoopPlan")
    assert hasattr(workloop, "OrchestrationLane")
    assert hasattr(verification, "VerificationEngine")
    assert hasattr(verification, "VerificationObligation")


def test_happy_work_loop_plan_and_verification_complete_with_five_obligations() -> None:
    from zeus_agent.verification_runtime import VerificationEngine, VerificationObligation
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: a compiled-objective-like contract with final-product acceptance criteria.
    contract = objective_contract()
    lanes = valid_lanes()
    obligations = passed_obligations()

    # When: a persistent work loop plan is built and verified.
    plan = WorkLoopBuilder().build(
        contract=contract,
        lanes=lanes,
        verification_obligations=obligations,
    )
    summary = VerificationEngine().evaluate(plan, obligations)

    # Then: completion is allowed only after every lane and obligation is evidence-ready.
    assert len(obligations) >= 5
    assert all(isinstance(obligation, VerificationObligation) for obligation in obligations)
    assert plan.goal_contract_id == "goal-final-workloop"
    assert plan.verification_obligations_count == 5
    assert plan.blocked_reasons == []
    assert plan.completion_allowed is True
    assert summary.verification_obligations_count == 5
    assert summary.blocked_reasons == []
    assert summary.completion_allowed is True
    assert summary.passed_obligation_ids == [
        "verify-workloop-lanes",
        "verify-lane-evidence-targets",
        "verify-runtime-obligations",
        "verify-manual-qa-channel",
        "verify-completion-gate",
    ]


def test_missing_lane_evidence_target_blocks_completion() -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: one lane has a stop condition but no evidence target.
    lanes = [
        *valid_lanes()[:-1],
        lane(
            "manual-qa",
            "harness/evidence/artifacts/final-qa.log",
            depends_on=["verification-runtime"],
            stop_condition="script PTY transcript captured by orchestrator",
            evidence_target=None,
        ),
    ]
    obligations = passed_obligations()

    # When: verification evaluates the plan.
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=lanes,
        verification_obligations=obligations,
    )
    summary = VerificationEngine().evaluate(plan, obligations)

    # Then: the lane blocks completion with a deterministic product-ready reason.
    assert plan.completion_allowed is False
    assert summary.completion_allowed is False
    assert summary.blocked_reasons == ["lane:manual-qa:missing_evidence_target"]


def test_planned_only_evidence_blocks_completion() -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: one accepted obligation is only mapped/planned rather than executed.
    obligations = [
        *passed_obligations()[:-1],
        obligation(
            "verify-completion-gate",
            "REQ-ZEUS-FINAL-003:S1",
            "completion-gate",
            obligation_type="gate",
            evidence_target="tests/test_final_workloop_verification.py::test_planned_only_evidence_blocks_completion",
            evidence_status="planned_only",
        ),
    ]

    # When: verification evaluates otherwise valid lanes.
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )
    summary = VerificationEngine().evaluate(plan, obligations)

    # Then: planned-only evidence is not enough to allow completion.
    assert summary.completion_allowed is False
    assert summary.blocked_reasons == ["obligation:verify-completion-gate:planned_only"]


def test_failed_obligation_blocks_completion() -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: a runtime obligation has failed evidence.
    obligations = [
        obligation(
            "verify-runtime-obligations",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            obligation_type="runtime",
            evidence_target="python3 -m compileall src/zeus_agent/verification_runtime",
            evidence_status="failed",
            failure_reason="compileall failed",
        ),
        *passed_obligations(),
    ]

    # When: verification evaluates the mixed obligation set.
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )
    summary = VerificationEngine().evaluate(plan, obligations)

    # Then: failed evidence blocks completion and reports the failing obligation first.
    assert summary.completion_allowed is False
    assert summary.blocked_reasons[0] == "obligation:verify-runtime-obligations:failed"
    assert "verify-runtime-obligations" not in summary.passed_obligation_ids


def test_missing_required_obligation_blocks_completion() -> None:
    from zeus_agent.verification_runtime import VerificationEngine
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: the completion gate expects one more obligation than the plan received.
    obligations = passed_obligations()[:-1]
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=obligations,
    )

    # When: verification is evaluated with an explicit required obligation list.
    summary = VerificationEngine().evaluate(
        plan,
        obligations,
        required_obligation_ids=[
            "verify-workloop-lanes",
            "verify-lane-evidence-targets",
            "verify-runtime-obligations",
            "verify-manual-qa-channel",
            "verify-completion-gate",
        ],
    )

    # Then: missing obligations are completion blockers.
    assert summary.completion_allowed is False
    assert summary.blocked_reasons == ["obligation:verify-completion-gate:missing"]


def test_lane_dependency_serialization_is_deterministic() -> None:
    from zeus_agent.workloop_runtime import WorkLoopBuilder

    # Given: lanes are provided out of order with unsorted dependencies and blockers.
    lanes = [
        lane(
            "verification-runtime",
            "src/zeus_agent/verification_runtime/**",
            depends_on=["workloop-runtime", "objective-runtime"],
            blocks=["manual-qa", "completion-gate"],
            stop_condition="verification summary emitted",
            evidence_target="tests/test_final_workloop_verification.py::test_lane_dependency_serialization_is_deterministic",
        ),
        lane(
            "objective-runtime",
            "src/zeus_agent/objective_runtime/**",
            blocks=["verification-runtime", "workloop-runtime"],
            stop_condition="objective contract emitted",
            evidence_target="docs/ai/current/Feature-Spec.md#REQ-ZEUS-FINAL-001",
        ),
        lane(
            "workloop-runtime",
            "src/zeus_agent/workloop_runtime/**",
            depends_on=["objective-runtime"],
            blocks=["verification-runtime"],
            stop_condition="work loop plan emitted",
            evidence_target="tests/test_final_workloop_verification.py::test_happy_work_loop_plan_and_verification_complete_with_five_obligations",
        ),
    ]

    # When: dependencies are serialized from the plan.
    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=lanes,
        verification_obligations=passed_obligations(),
    )

    # Then: lane ordering and edge lists are stable regardless of input order.
    assert [edge.model_dump(mode="json") for edge in plan.serialize_lane_dependencies()] == [
        {
            "lane_id": "objective-runtime",
            "depends_on": [],
            "blocks": ["verification-runtime", "workloop-runtime"],
        },
        {
            "lane_id": "verification-runtime",
            "depends_on": ["objective-runtime", "workloop-runtime"],
            "blocks": ["completion-gate", "manual-qa"],
        },
        {
            "lane_id": "workloop-runtime",
            "depends_on": ["objective-runtime"],
            "blocks": ["verification-runtime"],
        },
    ]
