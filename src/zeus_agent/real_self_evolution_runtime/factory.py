from __future__ import annotations

from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.real_self_evolution_runtime.models import RealSelfEvolutionContract
from zeus_agent.real_self_evolution_runtime.models import RealSelfEvolutionDecision
from zeus_agent.real_self_evolution_runtime.models import RealSelfEvolutionScenario

_TARGET_VERSION: Final = "v1.6.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.6.0.self_evolution_production_loop"


def build_contract(
    *,
    decision: RealSelfEvolutionDecision,
    scenario: RealSelfEvolutionScenario,
    blocked_reasons: tuple[str, ...] = (),
    skill_eval_contract: Optional[dict[str, JsonValue]] = None,
    skill_eval_registry_contract: Optional[dict[str, JsonValue]] = None,
    skill_learning_contract: Optional[dict[str, JsonValue]] = None,
    workflow_learning_contract: Optional[dict[str, JsonValue]] = None,
    skill_candidate_contract: Optional[dict[str, JsonValue]] = None,
    promotion_review_contract: Optional[dict[str, JsonValue]] = None,
    eval_learning_ready: bool = False,
    skill_proposal_ready: bool = False,
    workflow_critique_memory_ready: bool = False,
    promotion_block_ready: bool = False,
    real_self_evolution_ready: bool = False,
    eval_record_count: int = 0,
    learning_candidate_count: int = 0,
    skill_candidate_count: int = 0,
    fact_count: int = 0,
    eval_record_write_executed: bool = False,
    memory_write_executed: bool = False,
    raw_secret_marker_detected: bool = False,
    cleanup_performed: bool = False,
) -> RealSelfEvolutionContract:
    return RealSelfEvolutionContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="self_evolution_production_loop",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        eval_learning_ready=eval_learning_ready,
        skill_proposal_ready=skill_proposal_ready,
        workflow_critique_memory_ready=workflow_critique_memory_ready,
        promotion_block_ready=promotion_block_ready,
        real_self_evolution_ready=real_self_evolution_ready,
        production_ready=False,
        skill_eval_contract=skill_eval_contract,
        skill_eval_registry_contract=skill_eval_registry_contract,
        skill_learning_contract=skill_learning_contract,
        workflow_learning_contract=workflow_learning_contract,
        skill_candidate_contract=skill_candidate_contract,
        promotion_review_contract=promotion_review_contract,
        eval_record_count=eval_record_count,
        learning_candidate_count=learning_candidate_count,
        skill_candidate_count=skill_candidate_count,
        fact_count=fact_count,
        eval_record_write_executed=eval_record_write_executed,
        memory_write_executed=memory_write_executed,
        workflow_self_modification=False,
        workflow_memory_auto_write=False,
        workflow_pattern_promoted=False,
        memory_auto_promotion=False,
        skill_auto_promotion=False,
        active_skill_written=False,
        active_rule_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        raw_secret_marker_detected=raw_secret_marker_detected,
        raw_secret_returned=False,
        live_production_claimed=False,
        cleanup_performed=cleanup_performed,
    ).with_secret_scan()
