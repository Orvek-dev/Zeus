from __future__ import annotations

import json
from typing import Sequence

from zeus_agent.objective_runtime import ZeusObjectiveContract
from zeus_agent.product_runtime.models import ProductRuntimeSnapshot, WorkLoopContractAdapter
from zeus_agent.runtime_promotion import (
    LiveTransportPromotionRequest,
    RollbackPlan,
)
from zeus_agent.verification_runtime import VerificationObligation
from zeus_agent.workflow_runtime.jobs import RetryPolicy
from zeus_agent.workloop_runtime import OrchestrationLane, WorkLoopBuilder, WorkLoopPlan


def blocked_snapshot(
    contract: ZeusObjectiveContract,
    raw_secret: str,
) -> ProductRuntimeSnapshot:
    snapshot = ProductRuntimeSnapshot(
        objective_compiled=False,
        objective_id=contract.objective_id,
        work_loop_plan_created=False,
        work_loop_id="blocked",
        orchestration_lane_count=0,
        verification_obligations=len(contract.verification_obligations),
        verification_completion_allowed=False,
        promotion_live_transport=False,
        promotion_decision="blocked",
        promotion_reason="objective_blocked",
        handler_executed=False,
        network_opened=False,
        skill_evolution_candidate_status="not_created",
        skill_evolution_promoted=False,
        blocked_reasons=contract.block_reasons,
        adjacent_surface_still_works=False,
        no_secret_echo=True,
    )
    payload = snapshot.model_dump(mode="json")
    return ProductRuntimeSnapshot.model_validate(
        payload | {"no_secret_echo": raw_secret not in json.dumps(payload, sort_keys=True)},
    )


def work_loop_plan(
    contract: ZeusObjectiveContract,
    obligations: Sequence[VerificationObligation],
) -> WorkLoopPlan:
    adapter = WorkLoopContractAdapter(
        goal_contract_id=contract.objective_id,
        normalized_goal=contract.normalized_objective,
        deliverables=contract.deliverables,
        acceptance_criteria=[
            "REQ-ZEUS-FINAL-001:S1",
            "REQ-ZEUS-FINAL-002:S1",
            "REQ-ZEUS-FINAL-003:S1",
            "REQ-ZEUS-FINAL-004:S1",
            "REQ-ZEUS-FINAL-005:S1",
            "REQ-ZEUS-FINAL-006:S1",
        ],
    )
    return WorkLoopBuilder().build(
        contract=adapter,
        lanes=lanes(),
        verification_obligations=obligations,
        work_loop_id="workloop-final-architecture",
    )


def lanes() -> list[OrchestrationLane]:
    return [
        OrchestrationLane(
            lane_id="objective-runtime",
            owned_paths=["src/zeus_agent/objective_runtime/**"],
            depends_on=[],
            blocks=["workloop-runtime", "verification-runtime"],
            stop_condition="objective contract emitted",
            manual_qa_channel="script-pty",
            evidence_target=".omo/ulw-loop/evidence/final-g001-c001-core-contracts.txt",
        ),
        OrchestrationLane(
            lane_id="workloop-runtime",
            owned_paths=["src/zeus_agent/workloop_runtime/**"],
            depends_on=["objective-runtime"],
            blocks=["verification-runtime"],
            stop_condition="work loop plan emitted",
            manual_qa_channel="script-pty",
            evidence_target=".omo/ulw-loop/evidence/final-g001-c001-core-contracts.txt",
        ),
        OrchestrationLane(
            lane_id="verification-runtime",
            owned_paths=["src/zeus_agent/verification_runtime/**"],
            depends_on=["workloop-runtime"],
            blocks=["completion-gate"],
            stop_condition="verification summary emitted",
            manual_qa_channel="script-pty",
            evidence_target=".omo/ulw-loop/evidence/final-g001-c003-regression-gates.txt",
        ),
        OrchestrationLane(
            lane_id="skill-evolution",
            owned_paths=["src/zeus_agent/skill_evolution/**"],
            depends_on=["verification-runtime"],
            blocks=["completion-gate"],
            stop_condition="skill candidate remains proposed-only",
            manual_qa_channel="script-pty",
            evidence_target=".omo/ulw-loop/evidence/final-g001-c002-adversarial-blocks.txt",
        ),
        OrchestrationLane(
            lane_id="completion-gate",
            owned_paths=["docs/ai/current/Req-Evidence-Map.md"],
            depends_on=["verification-runtime", "skill-evolution"],
            blocks=[],
            stop_condition="all obligations verified before final report",
            manual_qa_channel="script-pty",
            evidence_target=".omo/ulw-loop/evidence/final-g001-c003-regression-gates.txt",
        ),
    ]


def passed_obligations() -> list[VerificationObligation]:
    return [
        _obligation(
            "verify-objective-contract",
            "REQ-ZEUS-FINAL-001:S1",
            "objective-runtime",
            ".omo/ulw-loop/evidence/final-g001-c001-core-contracts.txt",
        ),
        _obligation(
            "verify-workloop-plan",
            "REQ-ZEUS-FINAL-002:S1",
            "workloop-runtime",
            ".omo/ulw-loop/evidence/final-g001-c001-core-contracts.txt",
        ),
        _obligation(
            "verify-verification-engine",
            "REQ-ZEUS-FINAL-003:S1",
            "verification-runtime",
            ".omo/ulw-loop/evidence/final-g001-c003-regression-gates.txt",
        ),
        _obligation(
            "verify-promotion-block",
            "REQ-ZEUS-FINAL-004:S1",
            "verification-runtime",
            ".omo/ulw-loop/evidence/final-g001-c002-adversarial-blocks.txt",
        ),
        _obligation(
            "verify-skill-proposed-only",
            "REQ-ZEUS-FINAL-005:S1",
            "skill-evolution",
            ".omo/ulw-loop/evidence/final-g001-c002-adversarial-blocks.txt",
        ),
        _obligation(
            "verify-product-snapshot",
            "REQ-ZEUS-FINAL-006:S1",
            "completion-gate",
            ".omo/ulw-loop/evidence/final-g001-c003-regression-gates.txt",
        ),
    ]


def required_artifact_markers() -> dict[str, tuple[str, ...]]:
    return {
        "verify-objective-contract": (
            "objective_compiled=true",
            "work_loop_plan_created=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
        "verify-workloop-plan": (
            "work_loop_state_reload_stable=true",
            "work_loop_state_lane_steps>=5=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
        "verify-verification-engine": (
            "final_product_tests_passed=true",
            "governance_gates_ok=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
        "verify-promotion-block": (
            "live_transport_not_authorized_blocked=true",
            "handler_executed=false=true",
            "network_opened=false=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
        "verify-skill-proposed-only": (
            "unsafe_skill_auto_promotion_blocked=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
        "verify-product-snapshot": (
            "cli_eval_smoke_success=true",
            "independent_review_approval=true",
            "__QA_DONE__=0",
            "cleanup:",
        ),
    }


def promotion_request() -> LiveTransportPromotionRequest:
    return LiveTransportPromotionRequest(
        promotion_id="promotion-final-live-transport",
        capability_id="provider.external.generate",
        transport_kind="provider",
        idempotency_key="idem-final-promotion",
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0),
        rollback_plan=RollbackPlan(command="none", target="live_transport", executed=False),
        credential_scope="external.final.readonly",
        network_host="api.openai.local",
    )


def adjacent_surface_pass() -> bool:
    from zeus_agent.eval.wave8 import run_wave8_eval

    return run_wave8_eval()["failed"] == 0


def blocked_label(blocked: bool) -> str:
    return "blocked" if blocked else "allowed"


def dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _obligation(
    obligation_id: str,
    requirement_id: str,
    lane_id: str,
    evidence_target: str,
) -> VerificationObligation:
    return VerificationObligation(
        obligation_id=obligation_id,
        requirement_id=requirement_id,
        lane_id=lane_id,
        obligation_type="runtime",
        evidence_target=evidence_target,
        evidence_status="passed",
    )
