"""Conformance starter suite — the first 12 governed scenarios.

Each scenario is (host, capability, context) → expected decision + receipt
assertions, exactly as frozen in the control-plane design. This file seeds the
~40-scenario per-host suite that gates major versions (P5/P9): a major ships
only when a pinned host passes ≥95% of the full suite plus a 7-day soak.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zeus_agent.authority_compiler_runtime import (
    AuthorityEnvelope,
    EnvelopeStore,
    GrantTier,
    GrantedCapability,
    derive_child_authority,
)
from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityStore,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
    import_mcp_capability,
    reconcile_schema,
)
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    Obligation,
    ZeusDecisionEngine,
)
from zeus_agent.governor_runtime import BudgetScope
from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    FlightRecorder,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustDecision,
)

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
SESSION = "conformance.session"


def _record(
    capability_id: str,
    *,
    verb: VerbClass = VerbClass.fetch,
    side_effect: SideEffectClass = SideEffectClass.none,
    reversibility: Reversibility = Reversibility.reversible,
    status: CapabilityStatus = CapabilityStatus.active,
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=verb,
        title=capability_id,
        input_summary="in",
        output_summary="out",
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=status,
    )


def _store() -> CapabilityStore:
    return CapabilityStore(
        (
            _record("fs.read"),
            _record("fs.write", verb=VerbClass.store, side_effect=SideEffectClass.local_write),
            _record(
                "mail.send",
                verb=VerbClass.notify,
                side_effect=SideEffectClass.account_write,
                reversibility=Reversibility.compensable,
            ),
            _record(
                "vcs.push.public",
                verb=VerbClass.publish,
                side_effect=SideEffectClass.public_write,
                reversibility=Reversibility.compensable,
            ),
            _record("web.fetch"),
        )
    )


def _envelope() -> AuthorityEnvelope:
    return AuthorityEnvelope(
        envelope_id="env.conformance",
        objective_id="obj.conformance",
        principal_id="operator.local",
        granted=(
            GrantedCapability(capability_id="fs.read", tier=GrantTier.auto, provenance="clause.read"),
            GrantedCapability(
                capability_id="fs.write",
                tier=GrantTier.auto,
                provenance="clause.write",
                path_scopes=("/work/project",),
            ),
            GrantedCapability(
                capability_id="mail.send",
                tier=GrantTier.ask_first,
                provenance="clause.send",
                network_hosts=("smtp.example.com",),
            ),
        ),
    )


def _engine(tmp_path: Path) -> ZeusDecisionEngine:
    envelopes = EnvelopeStore()
    envelopes.put(_envelope())
    return ZeusDecisionEngine(
        recorder=FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3")),
        capabilities=_store(),
        envelopes=envelopes,
    )


def _request(
    capability_id: str,
    *,
    objective_id: str | None = "obj.conformance",
    session_id: str = SESSION,
    run_id: str = "run.conformance",
    args: dict | None = None,
) -> DecisionRequest:
    return DecisionRequest(
        principal_id="operator.local",
        session_id=session_id,
        run_id=run_id,
        capability_id=capability_id,
        args=args or {},
        context=DecisionContext(
            host=HostKind.claude_code,
            surface=GateSurface.hook,
            objective_id=objective_id,
        ),
    )


def _last_receipt_payloads(engine: ZeusDecisionEngine) -> list[str]:
    return [str(record["kind"]) for record in engine.recorder.ledger.records()]


# 1. read-only file → AUTO + evidence bound.
def test_scenario_01_read_only_auto_with_evidence(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("fs.read"), now=NOW)
    assert response.decision is TrustDecision.AUTO
    outcome_id = engine.record(
        response.receipt_id, ExecutionOutcome(status=ExecutionStatus.success)
    )
    chain = engine.recorder.why(outcome_id)
    assert str(chain[-1]["record_id"]) == response.receipt_id  # evidence bound to decision


# 2. local write in scope → AUTO.
def test_scenario_02_local_write_in_scope_auto(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(
        _request("fs.write", args={"path": "/work/project/src/main.py"}), now=NOW
    )
    assert response.decision is TrustDecision.AUTO
    out_of_scope = engine.decide(_request("fs.write", args={"path": "/etc/hosts"}), now=NOW)
    assert out_of_scope.decision is TrustDecision.ASK
    assert out_of_scope.reason == "path_outside_envelope_scope"


# 3. account write (mail.send) first time → ASK.
def test_scenario_03_account_write_first_time_asks(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("mail.send"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.parked_action_id is not None
    assert "decision_receipt" in _last_receipt_payloads(engine)


# 4. public write (git push public) → ASK + require_undo_plan.
def test_scenario_04_public_write_requires_undo_plan(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("vcs.push.public", objective_id=None), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert Obligation.require_undo_plan in response.obligations


# 5. quarantined MCP tool → DENY.
def test_scenario_05_quarantined_mcp_tool_denies(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    quarantined = import_mcp_capability(
        capability_id="mcp.foreign.tool",
        title="Foreign tool",
        verb_class=VerbClass.transform,
        input_summary="in",
        output_summary="out",
        schema_hash="hash-a",
        server_ref="server.x",
    )
    engine.capabilities.register(quarantined)
    response = engine.decide(_request("mcp.foreign.tool"), now=NOW)
    assert response.decision is TrustDecision.DENY
    assert response.reason == "capability_quarantined"
    assert response.receipt_id.startswith("trust.ev.")  # DENY still leaves a receipt


# 6. rug-pulled tool (hash changed) → DENY + re-quarantine.
def test_scenario_06_rug_pull_requarantines_and_denies(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    trusted = import_mcp_capability(
        capability_id="mcp.trusted.tool",
        title="Once-trusted tool",
        verb_class=VerbClass.transform,
        input_summary="in",
        output_summary="out",
        schema_hash="hash-original",
        server_ref="server.x",
    ).model_copy(update={"status": CapabilityStatus.active})
    engine.capabilities.register(trusted)
    assert engine.decide(_request("mcp.trusted.tool"), now=NOW).decision is not TrustDecision.DENY

    reconciled = reconcile_schema(trusted, observed_hash="hash-SWAPPED")
    assert reconciled.status is CapabilityStatus.quarantined  # re-quarantined
    assert reconciled.trust.runs == 0  # earned trust reset
    engine.capabilities.register(reconciled)
    response = engine.decide(_request("mcp.trusted.tool"), now=NOW)
    assert response.decision is TrustDecision.DENY


# 7. untrusted-then-external (trifecta #1) → ASK.
def test_scenario_07_untrusted_then_external_asks(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    fetch = engine.decide(_request("web.fetch"), now=NOW)
    assert fetch.decision is TrustDecision.AUTO
    engine.record(fetch.receipt_id, ExecutionOutcome(status=ExecutionStatus.success))
    response = engine.decide(_request("mail.send"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.reason == "untrusted_taint_reaches_external_sink"


# 8. private-to-nonapproved-host (#2) → DENY.
def test_scenario_08_private_to_unapproved_host_denies(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.capabilities.register(_record("credential.read"))
    secret = engine.decide(_request("credential.read"), now=NOW)
    engine.record(secret.receipt_id, ExecutionOutcome(status=ExecutionStatus.success))
    response = engine.decide(
        _request("mail.send", args={"network_host": "exfil.example.net"}), now=NOW
    )
    assert response.decision is TrustDecision.DENY
    assert response.reason == "private_taint_to_unapproved_host"


# 9. subagent out-of-envelope capability → DENY (derive_for_child raises).
def test_scenario_09_subagent_out_of_envelope_raises(tmp_path: Path) -> None:
    envelope = _envelope()
    child = derive_child_authority(
        envelope,
        run_id="run.conformance",
        child_principal_id="agent.child",
        requested_capabilities=("fs.read",),
    )
    assert child.allows("fs.read").decision == "allowed"
    with pytest.raises(ValueError, match="outside parent scope"):
        derive_child_authority(
            envelope,
            run_id="run.conformance",
            child_principal_id="agent.child",
            requested_capabilities=("vcs.push.public",),
        )


# 10. budget exhausted mid-loop → DENY (pre-call).
def test_scenario_10_budget_exhausted_denies_precall(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.governors.budget.set_limit(BudgetScope.objective, "obj.conformance", 3)
    first = engine.decide(_request("fs.read", run_id="run.loop"), now=NOW)
    assert first.decision is TrustDecision.AUTO
    engine.record(first.receipt_id, ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=3))
    response = engine.decide(_request("fs.read", run_id="run.loop"), now=NOW)
    assert response.decision is TrustDecision.DENY
    assert response.reason == "budget_exhausted_objective"


# 11. session grant downgrades repeat ASK → AUTO (not hard-risk).
def test_scenario_11_session_grant_downgrades_soft_ask(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    first = engine.decide(_request("mail.send"), now=NOW)
    assert first.decision is TrustDecision.ASK
    engine.grants.add(
        issue_grant(
            grant_id="grant.conformance.mail",
            capability_id="mail.send",
            scope=GrantScope.session,
            session_id=SESSION,
            expires_at_epoch=int((NOW + timedelta(hours=4)).timestamp()),
        )
    )
    second = engine.decide(_request("mail.send"), now=NOW)
    assert second.decision is TrustDecision.AUTO
    assert second.reason == "covered_by_grant_session"
    # the same grant must NOT cover a hard-risk public push
    hard = engine.decide(_request("vcs.push.public", objective_id=None), now=NOW)
    assert hard.decision is TrustDecision.ASK


# 12. ledger tamper → verify() fails.
def test_scenario_12_ledger_tamper_detected(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.decide(_request("fs.read"), now=NOW)
    assert engine.recorder.ledger.verify_chain().ok
    engine.recorder.ledger.force_tamper_for_test(1, {"decision": "auto", "forged": True})
    verification = engine.recorder.ledger.verify_chain()
    assert not verification.ok
    assert verification.reason == "payload_hash_mismatch"
