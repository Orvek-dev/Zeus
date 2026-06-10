from __future__ import annotations

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.objective_card_runtime import compile_objective_card
from zeus_agent.objective_risk_runtime import (
    BlastRadius,
    RiskClass,
    SafeDefault,
    Triage,
    Unknown,
)
from zeus_agent.workflow_fabric_runtime import (
    NodeKind,
    WorkflowCandidate,
    WorkflowEdge,
    WorkflowNode,
)


def _blog_unknowns() -> tuple[Unknown, ...]:
    return (
        Unknown(unknown_id="publish_target", description="Where should posts publish?",
                risk_class=RiskClass.external),
        Unknown(unknown_id="spend_cap", description="What is the monthly budget cap?",
                risk_class=RiskClass.cost),
        Unknown(unknown_id="frequency", description="How often to publish?", risk_class=RiskClass.time,
                blast_radius=BlastRadius.account, cost_bucket=2, failure_probability=0.4,
                safe_default=SafeDefault(value="twice weekly", rationale="conservative")),
        Unknown(unknown_id="tone", description="What tone?", risk_class=RiskClass.quality,
                sample_learnable=True),
    )


def _blog_gated_candidate() -> WorkflowCandidate:
    return WorkflowCandidate(
        candidate_id="blog.gated",
        nodes=(
            WorkflowNode(node_id="research", kind=NodeKind.llm_generic, cost_units=2,
                         produces_criteria=("topic_chosen",)),
            WorkflowNode(node_id="check_topic", kind=NodeKind.verification,
                         verifies_criteria=("topic_chosen",)),
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic, cost_units=3,
                         produces_criteria=("post_written",)),
            WorkflowNode(node_id="critic", kind=NodeKind.verification,
                         verifies_criteria=("post_written",)),
            WorkflowNode(node_id="approve", kind=NodeKind.approval_gate),
            WorkflowNode(node_id="publish", kind=NodeKind.capability,
                         capability_ref="mcp.blog.publish", side_effect=SideEffectClass.public_write,
                         cost_units=1),
        ),
        edges=(
            WorkflowEdge(src="research", dst="check_topic"),
            WorkflowEdge(src="check_topic", dst="draft"),
            WorkflowEdge(src="draft", dst="critic"),
            WorkflowEdge(src="critic", dst="approve"),
            WorkflowEdge(src="approve", dst="publish"),
        ),
    )


def test_blog_card_needs_answers_and_stages_publish_approval() -> None:
    card = compile_objective_card(
        normalized_objective="Automate my blog with AI",
        triage=Triage.automation,
        unknowns=_blog_unknowns(),
        candidates=(_blog_gated_candidate(),),
        required_criteria=("topic_chosen", "post_written"),
        budget_cap_units=20,
        projected_runs=8,
    )
    # Two hard-rule questions; cannot proceed without them.
    assert card.blocking_question_count == 2
    assert card.decision == "needs_answers"
    assert card.proceed_allowed_without_answers is False
    # The plan verified (publish is gated) and was chosen.
    assert card.chosen_workflow_id == "blog.gated"
    # Publish is staged for manual approval (earned-autonomy UX).
    stages = {stage.node_id: stage for stage in card.approval_stages}
    assert stages["publish"].manual_approvals_remaining == 3
    # Cost is projected across runs and stays within budget.
    assert card.cost.per_run_units == 6
    assert card.cost.projected_total_units == 48  # 6 * 8 ... over the cap
    assert card.cost.within_budget is False


def test_card_blocks_when_no_workflow_passes_verification() -> None:
    ungated = WorkflowCandidate(
        candidate_id="ungated",
        nodes=(WorkflowNode(node_id="publish", kind=NodeKind.capability,
                            capability_ref="mcp.blog.publish",
                            side_effect=SideEffectClass.public_write),),
    )
    card = compile_objective_card(
        normalized_objective="Just publish something",
        triage=Triage.oneshot,
        unknowns=(),
        candidates=(ungated,),
    )
    assert card.chosen_workflow_id is None
    assert card.decision == "blocked_no_verified_workflow"
    assert card.decision_record.reason == "all_candidates_failed_verification"


def test_card_surfaces_capability_gaps() -> None:
    candidate = WorkflowCandidate(
        candidate_id="withgap",
        nodes=(
            WorkflowNode(node_id="research", kind=NodeKind.llm_generic),
            WorkflowNode(node_id="publish", kind=NodeKind.gap,
                         missing_capability="mcp.tistory.publish_post"),
        ),
        edges=(WorkflowEdge(src="research", dst="publish"),),
    )
    card = compile_objective_card(
        normalized_objective="Post to Tistory",
        triage=Triage.project,
        unknowns=(),
        candidates=(candidate,),
    )
    assert card.capability_gaps == ("mcp.tistory.publish_post",)
    assert card.chosen_workflow_id == "withgap"
    assert card.decision_record.reason == "chosen_with_capability_gaps"
    # A plan with unconnected capabilities must NOT read as startable.
    assert card.decision == "needs_connections"


def test_tidy_folder_card_is_ready_to_start() -> None:
    unknowns = (
        Unknown(unknown_id="target_folder", description="Which folder?", risk_class=RiskClass.external,
                blast_radius=BlastRadius.local,
                safe_default=SafeDefault(value="~/Downloads", rationale="named in request")),
    )
    candidate = WorkflowCandidate(
        candidate_id="tidy",
        nodes=(
            WorkflowNode(node_id="scan", kind=NodeKind.llm_generic, produces_criteria=("scanned",)),
            WorkflowNode(node_id="check", kind=NodeKind.verification, verifies_criteria=("scanned",)),
            WorkflowNode(node_id="approve", kind=NodeKind.approval_gate),
            WorkflowNode(node_id="move", kind=NodeKind.capability, capability_ref="builtin.fs.move",
                         side_effect=SideEffectClass.local_write),
        ),
        edges=(
            WorkflowEdge(src="scan", dst="check"),
            WorkflowEdge(src="check", dst="approve"),
            WorkflowEdge(src="approve", dst="move"),
        ),
    )
    card = compile_objective_card(
        normalized_objective="Tidy my downloads folder",
        triage=Triage.oneshot,
        unknowns=unknowns,
        candidates=(candidate,),
        required_criteria=("scanned",),
    )
    assert card.blocking_question_count == 0
    assert card.decision == "ready_to_start"
    assert card.proceed_allowed_without_answers is True


# --- Codex review regressions: secret echo, projected budget, empty objective ---


def _clean_candidate(candidate_id: str = "clean") -> WorkflowCandidate:
    return WorkflowCandidate(
        candidate_id=candidate_id,
        nodes=(
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic, cost_units=6,
                         produces_criteria=("done",)),
            WorkflowNode(node_id="check", kind=NodeKind.verification, verifies_criteria=("done",)),
        ),
        edges=(WorkflowEdge(src="draft", dst="check"),),
    )


def test_secret_in_objective_blocks_and_never_echoes() -> None:
    card = compile_objective_card(
        normalized_objective="Use sk-proj-THISISSECRET to post updates",
        triage=Triage.oneshot,
        unknowns=(),
        candidates=(_clean_candidate(),),
    )
    assert card.decision == "blocked_raw_secret_material"
    assert card.chosen_workflow_id is None
    payload_text = str(card.to_payload())
    assert "THISISSECRET" not in payload_text
    assert card.no_secret_echo is True


def test_secret_markers_in_any_input_block_compilation() -> None:
    markers = (
        "ghp_THISISSECRETTOKEN",
        "Bearer THISISSECRETBEARER",
        "password=THISISSECRETPW",
    )
    for marker in markers:
        in_unknown = compile_objective_card(
            normalized_objective="Automate reporting",
            triage=Triage.oneshot,
            unknowns=(
                Unknown(unknown_id="cred", description="use {0}".format(marker),
                        risk_class=RiskClass.access),
            ),
            candidates=(_clean_candidate(),),
        )
        assert in_unknown.decision == "blocked_raw_secret_material"
        assert "THISISSECRET" not in str(in_unknown.to_payload())


def test_secret_in_safe_default_blocks() -> None:
    card = compile_objective_card(
        normalized_objective="Automate reporting",
        triage=Triage.oneshot,
        unknowns=(
            Unknown(unknown_id="key", description="api key to use", risk_class=RiskClass.access,
                    safe_default=SafeDefault(value="sk-proj-THISISSECRET", rationale="found in env")),
        ),
        candidates=(_clean_candidate(),),
    )
    assert card.decision == "blocked_raw_secret_material"
    assert "THISISSECRET" not in str(card.to_payload())


def test_projected_total_over_cap_blocks_start() -> None:
    # per_run=6, projected_runs=8 -> 48 > cap 20: must not be ready_to_start.
    card = compile_objective_card(
        normalized_objective="Run a weekly digest",
        triage=Triage.automation,
        unknowns=(),
        candidates=(_clean_candidate(),),
        required_criteria=("done",),
        budget_cap_units=20,
        projected_runs=8,
    )
    assert card.cost.projected_total_units == 48
    assert card.cost.within_budget is False
    assert card.decision == "over_budget"


def test_within_projected_budget_is_ready() -> None:
    card = compile_objective_card(
        normalized_objective="Run a weekly digest",
        triage=Triage.automation,
        unknowns=(),
        candidates=(_clean_candidate(),),
        required_criteria=("done",),
        budget_cap_units=60,
        projected_runs=8,
    )
    assert card.cost.within_budget is True
    assert card.decision == "ready_to_start"


def test_empty_objective_blocks() -> None:
    card = compile_objective_card(
        normalized_objective="   ",
        triage=Triage.oneshot,
        unknowns=(),
        candidates=(_clean_candidate(),),
    )
    assert card.decision == "blocked_empty_objective"
    assert card.normalized_objective == "[empty-objective]"
    assert card.chosen_workflow_id is None
