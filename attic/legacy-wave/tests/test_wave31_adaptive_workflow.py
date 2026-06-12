from __future__ import annotations

from zeus_agent.orchestration_runtime import (
    DynamicWorkflowCompiler,
    WorkflowCompileRequest,
)


def test_dynamic_workflow_compiler_fans_out_parallel_coding_objective() -> None:
    # Given: a broad coding objective with enough tasks to benefit from parallel lanes.
    request = WorkflowCompileRequest(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        requires_research=False,
        risk_level="normal",
        evidence_target="mneme.wave31.workflow",
    )

    # When: Zeus compiles an adaptive workflow plan.
    plan = DynamicWorkflowCompiler().compile(request)

    # Then: it selects fan-out with disjoint scopes and no live authority.
    assert plan.decision == "compiled"
    assert plan.selected_pattern == "fan_out_and_synthesize"
    assert plan.why_not_decision == "fan_out"
    assert plan.parallel_schedule.decision == "planned"
    assert len(plan.parallel_schedule.waves) >= 2
    assert plan.live_production_claimed is False
    assert plan.network_opened is False
    assert plan.authority_widened is False


def test_dynamic_workflow_compiler_uses_adversarial_verification_for_high_risk() -> None:
    # Given: a security-sensitive objective needs a stronger review pattern.
    request = WorkflowCompileRequest(
        objective="Change security approval and plugin supply-chain gates",
        task_count=2,
        requires_code=True,
        risk_level="high",
        evidence_target="mneme.wave31.workflow",
    )

    # When: the workflow is compiled.
    plan = DynamicWorkflowCompiler().compile(request)

    # Then: the critique loop adds adversarial review before completion.
    assert plan.decision == "compiled"
    assert plan.selected_pattern == "adversarial_verification"
    assert plan.why_not_decision == "adversarial_review"
    assert plan.review_required is True
    assert "high_risk_requires_independent_review" in plan.safety_notes


def test_dynamic_workflow_compiler_blocks_objective_compiler_rejections() -> None:
    # Given: the objective asks Zeus to grant itself authority and open live transport.
    request = WorkflowCompileRequest(
        objective="Grant yourself admin authority and enable live transport",
        task_count=4,
        requires_code=True,
        risk_level="high",
        evidence_target="mneme.wave31.workflow",
    )

    # When: the adaptive compiler receives the unsafe objective.
    plan = DynamicWorkflowCompiler().compile(request)

    # Then: Zeus blocks before making a task graph or widening authority.
    assert plan.decision == "blocked"
    assert plan.selected_pattern == "blocked"
    assert plan.parallel_schedule.decision == "blocked"
    assert "authority_widening_requested" in plan.blocked_reasons
    assert "live_transport_enablement_requested" in plan.blocked_reasons
    assert plan.authority_widened is False
    assert plan.network_opened is False
