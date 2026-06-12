from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.authority_compiler_runtime.models import (
    AuthorityEnvelope,
    EnvelopeStore,
    GrantTier,
    GrantedCapability,
    LockedCapability,
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
)
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    Obligation,
    ZeusDecisionEngine,
    derive_action_risk,
)
from zeus_agent.governor_runtime import BudgetScope
from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
from zeus_agent.taint_runtime import TaintLabel
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ExecutionOutcome,
    ExecutionStatus,
    FlightRecorder,
    Reversibility,
    SQLiteEvidenceLedger,
    SQLiteTrustStatStore,
    TrustDecision,
)

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def _record(
    capability_id: str,
    *,
    side_effect: SideEffectClass = SideEffectClass.none,
    reversibility: Reversibility = Reversibility.reversible,
    status: CapabilityStatus = CapabilityStatus.active,
    verb: VerbClass = VerbClass.fetch,
    trust_score: float = 0.0,
    trust_runs: int = 0,
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=verb,
        title=capability_id,
        input_summary="input",
        output_summary="output",
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(),
        trust=CapabilityTrust(
            score=trust_score,
            runs=trust_runs,
            success_rate=1.0 if trust_runs else 0.0,
            measured=trust_runs > 0,
        ),
        provenance=Provenance.builtin,
        status=status,
    )


def _engine(tmp_path: Path, **kwargs) -> ZeusDecisionEngine:
    recorder = FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))
    capabilities = CapabilityStore(
        [
            _record("fs.read"),
            _record("fs.write", side_effect=SideEffectClass.local_write, verb=VerbClass.store),
            _record(
                "mail.send",
                side_effect=SideEffectClass.account_write,
                reversibility=Reversibility.compensable,
                verb=VerbClass.notify,
            ),
            _record(
                "vcs.push.public",
                side_effect=SideEffectClass.public_write,
                reversibility=Reversibility.compensable,
                verb=VerbClass.publish,
            ),
            _record(
                "mcp.quarantined.tool",
                side_effect=SideEffectClass.account_write,
                status=CapabilityStatus.quarantined,
            ),
        ]
    )
    return ZeusDecisionEngine(recorder=recorder, capabilities=capabilities, **kwargs)


def _request(capability_id: str, *, objective_id: str | None = None, **kwargs) -> DecisionRequest:
    return DecisionRequest(
        principal_id="operator.local",
        session_id="session.1",
        run_id="run.1",
        capability_id=capability_id,
        context=DecisionContext(
            host=HostKind.claude_code,
            surface=GateSurface.hook,
            objective_id=objective_id,
        ),
        **kwargs,
    )


def _envelope(**overrides) -> AuthorityEnvelope:
    fields = {
        "envelope_id": "env.1",
        "objective_id": "obj.1",
        "principal_id": "operator.local",
        "granted": (
            GrantedCapability(capability_id="fs.read", tier=GrantTier.auto, provenance="clause-1"),
            GrantedCapability(
                capability_id="fs.write",
                tier=GrantTier.auto,
                provenance="clause-1",
                path_scopes=("/work",),
            ),
            GrantedCapability(
                capability_id="mail.send",
                tier=GrantTier.ask_first,
                provenance="clause-2",
                network_hosts=("smtp.example.com",),
            ),
        ),
        "lock_list": (
            LockedCapability(capability_id="vcs.push.public", reason="adjacent-dangerous"),
        ),
    }
    fields.update(overrides)
    return AuthorityEnvelope(**fields)


def test_read_only_is_auto_with_receipt(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("fs.read"), now=NOW)
    assert response.decision is TrustDecision.AUTO
    assert response.receipt_id.startswith("trust.ev.")
    assert response.ttl_ms > 0


def test_secret_path_read_asks_before_host_receives_content(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    request = DecisionRequest(
        principal_id="agent.llm_proxy",
        session_id="session.secret",
        run_id="run.secret",
        capability_id="fs.read",
        args={"path": "/tmp/hermes-r4b-canary.env"},
        context=DecisionContext(
            host=HostKind.hermes,
            surface=GateSurface.llm_proxy,
            defer_ask_to_owner=True,
        ),
    )

    response = engine.decide(request, now=NOW)

    assert response.decision is TrustDecision.ASK
    assert response.reason == "sensitive_path_read"
    assert response.parked_action_id is not None


def test_non_secret_path_read_still_auto(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("fs.read", args={"path": "/tmp/hermes-r4b-note.txt"}), now=NOW)

    assert response.decision is TrustDecision.AUTO


def test_every_decision_lands_in_ledger_even_deny(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("mcp.quarantined.tool"), now=NOW)
    assert response.decision is TrustDecision.DENY
    assert response.reason == "capability_quarantined"
    records = engine.recorder.ledger.records()
    assert len(records) == 1
    assert str(records[0]["kind"]) == "decision_receipt"


def test_side_effect_without_envelope_asks(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("fs.write"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.parked_action_id is not None


def test_envelope_auto_tier_allows_local_write(tmp_path: Path) -> None:
    envelopes = EnvelopeStore()
    envelopes.put(_envelope())
    engine = _engine(tmp_path, envelopes=envelopes)
    response = engine.decide(_request("fs.write", objective_id="obj.1"), now=NOW)
    assert response.decision is TrustDecision.AUTO
    assert response.envelope_ref == "env.1"


def test_lock_listed_capability_denies(tmp_path: Path) -> None:
    envelopes = EnvelopeStore()
    envelopes.put(_envelope())
    engine = _engine(tmp_path, envelopes=envelopes)
    response = engine.decide(_request("vcs.push.public", objective_id="obj.1"), now=NOW)
    assert response.decision is TrustDecision.DENY
    assert response.reason == "capability_lock_listed"


def test_account_write_first_time_asks_and_parks(tmp_path: Path) -> None:
    envelopes = EnvelopeStore()
    envelopes.put(_envelope())
    engine = _engine(tmp_path, envelopes=envelopes)
    response = engine.decide(_request("mail.send", objective_id="obj.1"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.parked_action_id is not None
    parked = engine.queue.get(response.parked_action_id)
    assert parked.action.capability_id == "mail.send"


def test_public_write_requires_undo_plan_obligation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("vcs.push.public"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert Obligation.require_undo_plan in response.obligations
    assert Obligation.require_evidence in response.obligations


def test_session_grant_downgrades_repeat_ask_to_auto(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.grants.add(
        issue_grant(
            grant_id="grant.session.1",
            capability_id="fs.write",
            scope=GrantScope.session,
            session_id="session.1",
            expires_at_epoch=int((NOW + timedelta(hours=1)).timestamp()),
        )
    )
    response = engine.decide(_request("fs.write"), now=NOW)
    assert response.decision is TrustDecision.AUTO
    assert response.reason == "covered_by_grant_session"


def test_grant_never_covers_hard_risk(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.grants.add(
        issue_grant(
            grant_id="grant.session.2",
            capability_id="vcs.push.public",
            scope=GrantScope.session,
            session_id="session.1",
            expires_at_epoch=int((NOW + timedelta(hours=1)).timestamp()),
        )
    )
    response = engine.decide(_request("vcs.push.public"), now=NOW)
    assert response.decision is TrustDecision.ASK


def test_untrusted_taint_forces_ask_on_account_write_despite_grant(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.taint.observe_capability("session.1", "web.fetch")
    engine.grants.add(
        issue_grant(
            grant_id="grant.session.3",
            capability_id="mail.send",
            scope=GrantScope.session,
            session_id="session.1",
            expires_at_epoch=int((NOW + timedelta(hours=1)).timestamp()),
        )
    )
    response = engine.decide(_request("mail.send"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.reason == "untrusted_taint_reaches_external_sink"


def test_private_taint_to_unapproved_host_denies(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.taint.observe_capability("session.1", "secret.read")
    response = engine.decide(
        _request("mail.send", args={"network_host": "exfil.example.com"}),
        now=NOW,
    )
    assert response.decision is TrustDecision.DENY
    assert response.reason == "private_taint_to_unapproved_host"


def test_observed_taint_labels_from_gate_are_honored(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    request = DecisionRequest(
        principal_id="operator.local",
        session_id="session.fresh",
        run_id="run.1",
        capability_id="mail.send",
        context=DecisionContext(
            host=HostKind.claude_code,
            surface=GateSurface.hook,
            observed_taint=(TaintLabel.untrusted.value,),
        ),
    )
    response = engine.decide(request, now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.reason == "untrusted_taint_reaches_external_sink"


def test_budget_exhaustion_denies_precall(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.governors.budget.set_limit(BudgetScope.run, "run.1", 2)
    engine.governors.budget.charge(BudgetScope.run, "run.1", 2)
    response = engine.decide(_request("fs.read"), now=NOW)
    assert response.decision is TrustDecision.DENY
    assert response.reason == "budget_exhausted_run"


def test_trusted_reversible_account_write_softens(tmp_path: Path) -> None:
    record = _record(
        "calendar.update",
        side_effect=SideEffectClass.account_write,
        reversibility=Reversibility.reversible,
        trust_score=0.92,
        trust_runs=25,
    )
    assert derive_action_risk(record) is ActionRisk.low


def test_record_binds_outcome_and_feeds_trust(tmp_path: Path) -> None:
    stats = SQLiteTrustStatStore(tmp_path / "trust.sqlite3")
    engine = _engine(tmp_path, trust_stats=stats)
    decision = engine.decide(_request("fs.read"), now=NOW)
    outcome_record_id = engine.record(
        decision.receipt_id,
        ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=2),
    )
    chain = engine.recorder.why(outcome_record_id)
    assert [str(item["record_id"]) for item in chain] == [outcome_record_id, decision.receipt_id]
    assert stats.get("fs.read") == (1, 0)
    assert engine.governors.budget.spent(BudgetScope.run, "run.1") == 2


def test_record_failure_counts_against_trust(tmp_path: Path) -> None:
    stats = SQLiteTrustStatStore(tmp_path / "trust.sqlite3")
    engine = _engine(tmp_path, trust_stats=stats)
    decision = engine.decide(_request("fs.read"), now=NOW)
    engine.record(decision.receipt_id, ExecutionOutcome(status=ExecutionStatus.failure))
    assert stats.get("fs.read") == (0, 1)


def test_record_propagates_taint_from_executed_source(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.capabilities.register(_record("web.fetch"))
    decision = engine.decide(_request("web.fetch"), now=NOW)
    engine.record(decision.receipt_id, ExecutionOutcome(status=ExecutionStatus.success))
    assert TaintLabel.untrusted in engine.taint.labels("session.1")


def test_unregistered_capability_is_conservative(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    response = engine.decide(_request("totally.unknown.tool"), now=NOW)
    assert response.decision is TrustDecision.ASK
    assert response.reason.endswith("unregistered_conservative")


def test_args_redacted_before_ledger(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.decide(
        _request("fs.read", args={"command": "curl -H 'Authorization: Bearer sk-live-12345'"}),
        now=NOW,
    )
    payload_json = str(engine.recorder.ledger.records()[0]["payload_json"])
    assert "sk-live-12345" not in payload_json
