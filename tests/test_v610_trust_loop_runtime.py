from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustDecision,
    TrustLoopAction,
    TrustPolicyProfile,
    UndoPlan,
)


def test_trust_loop_denies_unknown_capability_before_handler(tmp_path: Path) -> None:
    # Given: a dispatcher with no registered capability for the requested action.
    calls: list[str] = []
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=CapabilityGraph(()),
        handlers={"provider.fake.generate": lambda _payload: calls.append("called")},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
    )

    # When: the action tries to execute an unknown capability.
    receipt = dispatcher.dispatch(
        _action(capability_id="provider.unknown.generate"),
        lease=_lease(("provider.unknown.generate",)),
    )

    # Then: the action is denied before the handler can run and evidence is recorded.
    assert receipt.decision == TrustDecision.DENY
    assert receipt.handler_executed is False
    assert receipt.blocked_reason == "unknown_capability"
    assert calls == []
    assert receipt.evidence_record_id.startswith("trust.ev.")


def test_trust_loop_requires_approval_for_irreversible_action(tmp_path: Path) -> None:
    # Given: an irreversible action whose lease is otherwise valid.
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=_graph("provider.external.generate", CapabilityRisk.high),
        handlers={"provider.external.generate": lambda _payload: {"status": "sent"}},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
    )

    # When: it is dispatched without an approval envelope.
    receipt = dispatcher.dispatch(
        _action(
            capability_id="provider.external.generate",
            risk=ActionRisk.high,
            reversibility=Reversibility.irreversible,
        ),
        lease=_lease(("provider.external.generate",)),
    )

    # Then: the trust loop asks for human approval and does not execute.
    assert receipt.decision == TrustDecision.ASK
    assert receipt.handler_executed is False
    assert receipt.blocked_reason == "approval_required"


def test_trust_loop_auto_executes_reversible_in_scope_action_with_evidence(
    tmp_path: Path,
) -> None:
    # Given: a low-risk reversible action inside its lease and budget.
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=_graph("provider.fake.generate", CapabilityRisk.low),
        handlers={"provider.fake.generate": lambda payload: {"echo": payload["prompt"]}},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
    )

    # When: it is dispatched through the governed spine.
    receipt = dispatcher.dispatch(
        _action(capability_id="provider.fake.generate", payload={"prompt": "hello"}),
        lease=_lease(("provider.fake.generate",)),
    )

    # Then: it executes through CapabilityBroker and gets append-only evidence.
    assert receipt.decision == TrustDecision.AUTO
    assert receipt.handler_executed is True
    assert receipt.broker_evidence_bound is True
    assert receipt.result == {"echo": "hello"}
    assert receipt.cleanup_receipt_id.startswith("trust.cleanup.")
    assert dispatcher.ledger.verify_chain().ok is True


def test_trust_loop_blocks_tainted_medium_action_from_auto_notify(
    tmp_path: Path,
) -> None:
    # Given: a medium-risk reversible action with tainted input.
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=_graph("gateway.webhook.dispatch", CapabilityRisk.medium),
        handlers={"gateway.webhook.dispatch": lambda _payload: {"status": "delivered"}},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
        policy=TrustPolicyProfile.balanced,
    )

    # When: it is dispatched with a taint-sensitive flag.
    receipt = dispatcher.dispatch(
        _action(
            capability_id="gateway.webhook.dispatch",
            risk=ActionRisk.medium,
            reversibility=Reversibility.compensable,
            tainted=True,
            taint_sensitive=True,
        ),
        lease=_lease(("gateway.webhook.dispatch",)),
    )

    # Then: it escalates to ASK instead of silently executing.
    assert receipt.decision == TrustDecision.ASK
    assert receipt.handler_executed is False
    assert receipt.blocked_reason == "tainted_medium_risk_requires_approval"


def test_evidence_ledger_detects_tamper_and_redacts_secret(tmp_path: Path) -> None:
    # Given: a hash-chained ledger that receives secret-like payload data.
    ledger = SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3")

    # When: evidence is appended and the stored row is tampered with.
    event = ledger.append(
        kind="decision_receipt",
        run_id="v610.run.trust",
        payload={"api_key": "sk-test-secret", "decision": "blocked"},
    )
    ledger.force_tamper_for_test(event.seq, {"decision": "allowed"})

    # Then: raw secrets are not stored and the chain verification fails.
    serialized = json.dumps(ledger.records(), sort_keys=True)
    assert "sk-test-secret" not in serialized
    assert ledger.verify_chain().ok is False


def test_trust_loop_approval_envelope_requires_undo_for_reversible_execution(
    tmp_path: Path,
) -> None:
    # Given: a high-risk compensable action with explicit approval and undo plan.
    capability_id = "terminal.run"
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=_graph(capability_id, CapabilityRisk.high, SideEffect.local_process),
        handlers={capability_id: lambda _payload: {"status": "ok"}},
        ledger=SQLiteEvidenceLedger(tmp_path / "trust-loop.sqlite3"),
    )

    # When: the approval envelope proves the undo path before execution.
    receipt = dispatcher.dispatch(
        _action(
            capability_id=capability_id,
            risk=ActionRisk.high,
            reversibility=Reversibility.compensable,
        ),
        lease=_lease((capability_id,)),
        approval=_approval(capability_id),
        approval_envelope=ApprovalEnvelope(
            envelope_id="trust.approval.terminal",
            capability_id=capability_id,
            approval_receipt_id="trust.receipt.terminal",
            predicted_effects=("run local command",),
            reversibility=Reversibility.compensable,
            undo_plan=UndoPlan(
                plan_id="trust.undo.terminal",
                strategy="compensating_tx",
                snapshot_ref="trust.snapshot.terminal",
            ),
            risk=ActionRisk.high,
            budget=BudgetEnvelope(max_units=10, requested_units=1),
        ),
    )

    # Then: it can run, records an undo token, and remains evidence-bound.
    assert receipt.decision == TrustDecision.ASK
    assert receipt.handler_executed is True
    assert receipt.approval_bound is True
    assert receipt.undo_token_id == "trust.undo.terminal"
    assert dispatcher.ledger.verify_chain().ok is True


def test_release_gate_recognizes_v610_trust_loop_checkpoint() -> None:
    # Given: the v6.1.0 release checkpoint is requested.
    status = build_release_gated_ulw_status(target_version="v6.1.0")

    # When: Zeus builds the release gate payload.
    payload = status.to_payload()

    # Then: the release is known and requires Trust Loop refoundation evidence.
    assert payload["decision"] == "report"
    assert payload["release_stage"] == "trust_loop_refoundation"
    assert "trust_loop_runtime_spine_tests" in payload["required_checkpoint_evidence"]


def _action(
    *,
    capability_id: str,
    payload: dict[str, str] | None = None,
    risk: ActionRisk = ActionRisk.low,
    reversibility: Reversibility = Reversibility.reversible,
    tainted: bool = False,
    taint_sensitive: bool = False,
) -> TrustLoopAction:
    return TrustLoopAction(
        action_id="trust.action.{0}".format(capability_id.replace(".", "_")),
        run_id="v610.run.trust",
        goal_contract_id="v610.objective.trust",
        criterion_id="REQ-ZEUS-TRUST-610:S1",
        capability_id=capability_id,
        payload=payload or {},
        risk=risk,
        reversibility=reversibility,
        tainted=tainted,
        taint_sensitive=taint_sensitive,
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
        live_transport_allowed=False,
        issued_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def _approval(capability_id: str) -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="v610.principal.operator",
        run_id="v610.run.trust",
        goal_contract_id="v610.objective.trust",
        approved_capabilities=[capability_id],
        nonce="trust.approval.nonce",
    )


def _graph(
    capability_id: str,
    risk: CapabilityRisk,
    side_effect: SideEffect = SideEffect.none,
) -> CapabilityGraph:
    return CapabilityGraph(
        (
            CapabilityDescriptor(
                capability_id=capability_id,
                name=capability_id.replace(".", "_"),
                risk=risk,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                side_effects=() if side_effect == SideEffect.none else (side_effect,),
            ),
        ),
    )
