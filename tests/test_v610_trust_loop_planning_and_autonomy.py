from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityGraph, CapabilityRisk
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalQueue,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    PlanCandidate,
    PlanTournament,
    Reversibility,
    SQLiteEvidenceLedger,
    SkillManifest,
    TrustDecision,
    TrustLedger,
    TrustLoopAction,
)


def test_approval_queue_supersedes_old_parked_action() -> None:
    # Given: the same action is parked twice while awaiting human approval.
    queue = ApprovalQueue()
    first = queue.park(_action("terminal.run"))
    second = queue.park(_action("terminal.run"))

    # When: the operator inspects pending approvals.
    pending = queue.pending(now=datetime.now(timezone.utc))

    # Then: only the latest action remains pending and the first is superseded.
    assert first.status == "pending"
    assert second.status == "pending"
    assert queue.get(first.parked_action_id).status == "superseded"
    assert tuple(item.parked_action_id for item in pending) == (second.parked_action_id,)


def test_plan_tournament_prefers_verified_lower_cost_plan() -> None:
    # Given: several plans cover the same goal with different risk and evidence quality.
    tournament = PlanTournament()
    risky = PlanCandidate(
        plan_id="plan.risky",
        task_ids=("task.a", "task.b"),
        required_capabilities=("provider.external.generate",),
        acceptance_criteria=("criterion.a", "criterion.b"),
        verification_obligations=("unit",),
        risk=ActionRisk.high,
        cost_units=4,
    )
    balanced = PlanCandidate(
        plan_id="plan.balanced",
        task_ids=("task.a", "task.b"),
        required_capabilities=("provider.fake.generate",),
        acceptance_criteria=("criterion.a", "criterion.b"),
        verification_obligations=("unit", "integration"),
        risk=ActionRisk.low,
        cost_units=2,
    )

    # When: Zeus selects the plan for execution.
    selected = tournament.select((risky, balanced))

    # Then: the lower-risk plan with stronger verification wins.
    assert selected.plan_id == "plan.balanced"
    assert selected.verification_obligations == ("unit", "integration")


def test_trust_ledger_proposes_but_does_not_auto_grant() -> None:
    # Given: repeated successful evidence for a reversible low-risk capability.
    ledger = TrustLedger()
    action = _action("provider.fake.generate")
    for _index in range(3):
        ledger.record_success(action)

    # When: the trust ledger evaluates progressive autonomy.
    proposal = ledger.propose_grant(action)

    # Then: Zeus only proposes scoped autonomy and never activates it directly.
    assert proposal is not None
    assert proposal.capability_id == "provider.fake.generate"
    assert proposal.auto_applied is False
    assert proposal.requires_human_review is True


def test_skill_manifest_blocks_dispatch_outside_declared_capabilities(
    tmp_path: Path,
) -> None:
    # Given: a skill manifest declares only provider.fake.generate.
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=CapabilityGraph(
            (
                CapabilityDescriptor(
                    capability_id="terminal.run",
                    name="terminal_run",
                    risk=CapabilityRisk.low,
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                ),
            ),
        ),
        handlers={"terminal.run": lambda _payload: {"status": "ok"}},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
        skill_manifest=SkillManifest(
            skill_id="skill.safe.fake",
            allowed_capabilities=("provider.fake.generate",),
        ),
    )

    # When: the skill tries to dispatch terminal.run.
    receipt = dispatcher.dispatch(
        _action("terminal.run"),
        lease=_lease(("terminal.run",)),
    )

    # Then: INV-5 blocks the action before handler execution.
    assert receipt.decision == TrustDecision.DENY
    assert receipt.blocked_reason == "skill_manifest_capability_blocked"
    assert receipt.handler_executed is False


def _action(capability_id: str) -> TrustLoopAction:
    return TrustLoopAction(
        action_id="trust.action.{0}".format(capability_id.replace(".", "_")),
        run_id="v610.run.trust",
        goal_contract_id="v610.objective.trust",
        criterion_id="REQ-ZEUS-TRUST-610:S2",
        capability_id=capability_id,
        risk=ActionRisk.low,
        reversibility=Reversibility.reversible,
        budget=BudgetEnvelope(max_units=10, requested_units=1),
    )


def _lease(capabilities: tuple[str, ...]) -> RuntimeLease:
    return RuntimeLease(
        lease_id="v610.lease.trust",
        objective_id="v610.objective.trust",
        principal_id="v610.principal.operator",
        run_id="v610.run.trust",
        allowed_capabilities=capabilities,
        budget_limit=10,
        evidence_target="mneme.v610.trust_loop",
        issued_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
