from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final, Optional

from zeus_agent.orchestration_runtime import WorkflowCompileRequest
from zeus_agent.real_self_evolution_runtime.factory import build_contract
from zeus_agent.real_self_evolution_runtime.models import RealSelfEvolutionContract
from zeus_agent.real_self_evolution_runtime.models import RealSelfEvolutionScenario
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_evolution import generate_skill_evolution_candidate
from zeus_agent.skill_evolution import review_skill_promotion
from zeus_agent.skill_learning_runtime import SkillLearningRuntime
from zeus_agent.workflow_learning_runtime import WorkflowCritiqueMemoryRuntime

_DEFAULT_CANDIDATE_ID: Final = "review-checklist"
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "eval-learning-smoke",
        "skill-proposal-smoke",
        "workflow-critique-memory",
        "promotion-block",
    },
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)


def build_real_self_evolution_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    objective: str = "Improve Zeus governed workflow efficiency from verified eval evidence.",
) -> RealSelfEvolutionContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return build_contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_self_evolution_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if _has_secret_marker(objective):
        return build_contract(
            decision="blocked",
            scenario=parsed_scenario,
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    if parsed_scenario == "status":
        return build_contract(decision="report", scenario="status")
    if home is not None:
        return _build(parsed_scenario, home=home, objective=objective, cleanup_performed=False)
    with tempfile.TemporaryDirectory(prefix="zeus-v160-self-evolution-") as raw_home:
        return _build(parsed_scenario, home=Path(raw_home), objective=objective, cleanup_performed=True)


def _build(
    scenario: RealSelfEvolutionScenario,
    *,
    home: Path,
    objective: str,
    cleanup_performed: bool,
) -> RealSelfEvolutionContract:
    if scenario == "eval-learning-smoke":
        return _eval_learning_smoke(home=home, cleanup_performed=cleanup_performed)
    if scenario == "skill-proposal-smoke":
        return _skill_proposal_smoke(cleanup_performed=cleanup_performed)
    if scenario == "workflow-critique-memory":
        return _workflow_critique_memory(
            home=home,
            objective=objective,
            cleanup_performed=cleanup_performed,
        )
    return _promotion_block(cleanup_performed=cleanup_performed)


def _eval_learning_smoke(*, home: Path, cleanup_performed: bool) -> RealSelfEvolutionContract:
    eval_result = SkillEvalRuntime(home).evaluate(candidate_id=_DEFAULT_CANDIDATE_ID)
    registry = SkillEvalRegistryRuntime(home).record(
        eval_result=eval_result,
        eval_ref="skill-eval://v160/self-evolution",
    )
    learning = SkillLearningRuntime(home).build()
    ready = (
        eval_result.decision == "evaluated"
        and registry.decision == "recorded"
        and learning.decision == "report"
        and learning.learning_candidate_count >= 1
        and not learning.active_skill_written
        and not learning.active_rule_written
        and learning.no_secret_echo
    )
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="eval-learning-smoke",
        blocked_reasons=()
        if ready
        else (*eval_result.blocked_reasons, *registry.blocked_reasons, *learning.blocked_reasons),
        skill_eval_contract=eval_result.to_payload(),
        skill_eval_registry_contract=registry.to_payload(),
        skill_learning_contract=learning.to_payload(),
        eval_learning_ready=ready,
        real_self_evolution_ready=ready,
        eval_record_count=registry.record_count,
        learning_candidate_count=learning.learning_candidate_count,
        eval_record_write_executed=registry.decision == "recorded",
        cleanup_performed=cleanup_performed,
    )


def _skill_proposal_smoke(*, cleanup_performed: bool) -> RealSelfEvolutionContract:
    candidate = generate_skill_evolution_candidate(
        evidence_summary="Repeated eval evidence shows workflow preflight should warn before recurring failure.",
        repeated_failure_tags=("verification-taught-loop", "self-evolution"),
        improvement_rationale="Propose a reviewed skill rule from verified eval evidence without activating it.",
        source_evidence_ids=("v160.skill-proposal-smoke",),
    )
    review = review_skill_promotion(candidate, explicit_approval=False)
    ready = review.status == "review_required" and not review.promoted and not review.authority_delta_allowed
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="skill-proposal-smoke",
        blocked_reasons=tuple(review.blocked_reasons),
        skill_candidate_contract=candidate.model_dump(mode="json"),
        promotion_review_contract=review.model_dump(mode="json"),
        skill_proposal_ready=ready,
        real_self_evolution_ready=ready,
        skill_candidate_count=1,
        cleanup_performed=cleanup_performed,
    )


def _workflow_critique_memory(
    *,
    home: Path,
    objective: str,
    cleanup_performed: bool,
) -> RealSelfEvolutionContract:
    request = WorkflowCompileRequest(
        objective=objective,
        task_count=8,
        requires_code=True,
        requires_research=True,
        risk_level="normal",
        evidence_target="v160.workflow-critique-memory",
    )
    workflow = WorkflowCritiqueMemoryRuntime(home).record(request=request)
    ready = (
        workflow.decision == "recorded"
        and workflow.fact_count >= 1
        and not workflow.memory_promoted
        and not workflow.authority_widened
        and workflow.no_secret_echo
    )
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="workflow-critique-memory",
        blocked_reasons=() if ready else workflow.blocked_reasons,
        workflow_learning_contract=workflow.to_payload(),
        workflow_critique_memory_ready=ready,
        real_self_evolution_ready=ready,
        fact_count=workflow.fact_count,
        memory_write_executed=workflow.decision == "recorded",
        cleanup_performed=cleanup_performed,
    )


def _promotion_block(*, cleanup_performed: bool) -> RealSelfEvolutionContract:
    candidate = generate_skill_evolution_candidate(
        evidence_summary="Do not auto promote raw learning logs into active skills.",
        repeated_failure_tags=("auto-promotion", "self-evolution"),
        improvement_rationale="Auto promote to active skill after one passing eval.",
        source_evidence_ids=("v160.promotion-block",),
    )
    review = review_skill_promotion(candidate, explicit_approval=False, requested_authority_delta=True)
    ready = not review.promoted and "explicit_review_required" in review.blocked_reasons
    return build_contract(
        decision="blocked",
        scenario="promotion-block",
        blocked_reasons=tuple(review.blocked_reasons),
        skill_candidate_contract=candidate.model_dump(mode="json"),
        promotion_review_contract=review.model_dump(mode="json"),
        promotion_block_ready=ready,
        real_self_evolution_ready=ready,
        skill_candidate_count=1,
        cleanup_performed=cleanup_performed,
    )


def _parse_scenario(value: str) -> RealSelfEvolutionScenario:
    if value == "status":
        return "status"
    if value == "eval-learning-smoke":
        return "eval-learning-smoke"
    if value == "skill-proposal-smoke":
        return "skill-proposal-smoke"
    if value == "workflow-critique-memory":
        return "workflow-critique-memory"
    return "promotion-block"


def _has_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
