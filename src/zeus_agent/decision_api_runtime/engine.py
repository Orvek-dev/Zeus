from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Final, Optional

from pydantic import JsonValue

from zeus_agent.authority_compiler_runtime.models import (
    AuthorityEnvelope,
    EnvelopeStore,
    GrantTier,
    GrantedCapability,
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
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.graded_approval_runtime import GrantScope, GrantStore
from zeus_agent.taint_runtime import (
    SessionTaintTracker,
    TaintLabel,
    assess_action,
    is_external_send,
    is_private_source,
)
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalQueue,
    BudgetEnvelope,
    ExecutionOutcome,
    ExecutionStatus,
    FlightRecorder,
    ReplayAuthorizationStore,
    Reversibility,
    SQLiteTrustStatStore,
    TrustDecision,
    TrustDecisionEngine,
    TrustLoopAction,
    TrustPolicyProfile,
    replay_payload_hash,
)
from zeus_agent.trust_loop_runtime.ledger import _redact_json

from .models import DecisionRequest, DecisionResponse, Obligation

_AUTO_TTL_MS: Final = 30_000

_RISK_ORDER: Final[tuple[ActionRisk, ...]] = (ActionRisk.low, ActionRisk.medium, ActionRisk.high)

_BASE_RISK_BY_SIDE_EFFECT: Final[dict[SideEffectClass, ActionRisk]] = {
    SideEffectClass.none: ActionRisk.low,
    SideEffectClass.local_write: ActionRisk.low,
    SideEffectClass.account_write: ActionRisk.medium,
    SideEffectClass.public_write: ActionRisk.high,
}

# Trust earned from real receipts can soften ONE level, and only for
# reversible writes at account scope or below — never for public/irreversible.
_TRUST_SOFTEN_THRESHOLD: Final = 0.8


def derive_action_risk(record: CapabilityRecord, *, escalation: int = 0) -> ActionRisk:
    """Deterministic risk from (side effect × reversibility × trust)."""
    index = _RISK_ORDER.index(_BASE_RISK_BY_SIDE_EFFECT[record.side_effect])
    if record.reversibility is Reversibility.irreversible:
        index += 1
    if (
        record.trust.measured
        and record.trust.score >= _TRUST_SOFTEN_THRESHOLD
        and record.reversibility is Reversibility.reversible
        and record.side_effect in {SideEffectClass.local_write, SideEffectClass.account_write}
    ):
        index -= 1
    index += max(escalation, 0)
    return _RISK_ORDER[min(max(index, 0), len(_RISK_ORDER) - 1)]


def conservative_record_for(capability_id: str) -> CapabilityRecord:
    """Fail-closed stand-in for a capability nobody registered: assumed to
    write at account scope, irreversibly, with zero earned trust."""
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=VerbClass.transform,
        title="Unregistered capability",
        input_summary="unknown",
        output_summary="unknown",
        side_effect=SideEffectClass.account_write,
        reversibility=Reversibility.irreversible,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


class ZeusDecisionEngine:
    """decide()/record() — the two-endpoint Decision API (P0).

    In control-plane mode Zeus DECIDES and RECORDS; the host EXECUTES its own
    tool. Nothing in this engine performs I/O on the action's behalf.
    """

    def __init__(
        self,
        *,
        recorder: FlightRecorder,
        capabilities: Optional[CapabilityStore] = None,
        envelopes: Optional[EnvelopeStore] = None,
        taint: Optional[SessionTaintTracker] = None,
        governors: Optional[GovernorBank] = None,
        grants: Optional[GrantStore] = None,
        queue: Optional[ApprovalQueue] = None,
        replay_authorizations: Optional[ReplayAuthorizationStore] = None,
        trust_stats: Optional[SQLiteTrustStatStore] = None,
        policy_profile: TrustPolicyProfile = TrustPolicyProfile.cautious,
        approved_hosts: tuple[str, ...] = (),
        seq_counter: Optional[Callable[[], int]] = None,
        explainability: Optional[Callable[[CapabilityRecord], bool]] = None,
    ) -> None:
        self.recorder = recorder
        self.capabilities = capabilities if capabilities is not None else CapabilityStore()
        self.envelopes = envelopes if envelopes is not None else EnvelopeStore()
        self.taint = taint if taint is not None else SessionTaintTracker()
        self.governors = governors if governors is not None else GovernorBank()
        self.grants = grants if grants is not None else GrantStore()
        self.queue = queue if queue is not None else ApprovalQueue()
        self.replay_authorizations = replay_authorizations
        self.trust_stats = trust_stats
        self._policy = TrustDecisionEngine(policy_profile)
        self._approved_hosts = approved_hosts
        # seq_counter (e.g. SQLiteControlPlaneStore.next_counter) keeps action
        # ids unique across one-decision-per-process gates; the in-memory
        # fallback only serves a single engine lifetime.
        self._seq_counter = seq_counter
        self._decision_seq = 0
        # explainability(record) -> bool: can this capability be described in a
        # vetted plain-language card? Injected (not imported) to avoid the cycle
        # with consequence_runtime. None → the rule is off (e.g. bare engine in
        # a unit test); every product gate wires it in build_engine().
        self._explainability = explainability

    # ------------------------------------------------------------------ decide
    def decide(self, request: DecisionRequest, *, now: Optional[datetime] = None) -> DecisionResponse:
        timestamp = now if now is not None else datetime.now(timezone.utc)
        args = _redact_args(request.args)
        network_host = _text_or_none(args.get("network_host"))
        path = _text_or_none(args.get("path"))

        # 1. active envelope (least-authority contract) for the objective.
        envelope = self.envelopes.active_for(request.context.objective_id, now=timestamp)

        # 2. capability record; quarantined → DENY immediately.
        record = self.capabilities.get(request.capability_id)
        record_known = record is not None
        if record is None:
            record = conservative_record_for(request.capability_id)
        if record.status is CapabilityStatus.quarantined:
            return self._finalize(
                request, args, TrustDecision.DENY, "capability_quarantined",
                envelope=envelope, record=record,
            )
        if envelope is not None and envelope.locked(request.capability_id) is not None:
            return self._finalize(
                request, args, TrustDecision.DENY, "capability_lock_listed",
                envelope=envelope, record=record,
            )

        # 2.5 hard boundary the gate already failed (egress ring, etc.). Same
        # class as quarantine — a wall, not a judgement — so the same
        # pre-decision short-circuit: the receipt records the DENY truthfully
        # and no gate ever mutates an AUTO response after the fact.
        if request.context.boundary_violation is not None:
            return self._finalize(
                request, args, TrustDecision.DENY, request.context.boundary_violation,
                envelope=envelope, record=record,
            )

        # 3. taint overlay → TrustLoopAction risk/flags.
        live_labels = set(self.taint.labels(request.session_id))
        for label in request.context.observed_taint:
            try:
                live_labels.add(TaintLabel(label))
            except ValueError:
                continue
        approved_hosts: frozenset[str] = (
            envelope.approved_hosts() if envelope is not None else frozenset(self._approved_hosts)
        )
        assessment = assess_action(
            live_labels=live_labels,
            side_effect=record.side_effect,
            network_host=network_host,
            approved_hosts=approved_hosts,
            credential_access=(
                is_private_source(request.capability_id)
                or _text_or_none(args.get("credential_scope")) is not None
            ),
            external_send=is_external_send(request.capability_id, network_host=network_host),
        )
        if assessment.forced_decision is TrustDecision.DENY:
            return self._finalize(
                request, args, TrustDecision.DENY, assessment.reasons[0],
                envelope=envelope, record=record,
            )
        risk = derive_action_risk(record, escalation=assessment.risk_escalation)
        hard_risk = risk is ActionRisk.high or record.reversibility is Reversibility.irreversible

        # 4. standing graded grant (license) — never covers hard risk. Looked
        # up without consuming; a once-grant burns only if it actually applies.
        grant = self.grants.covering(
            capability_id=request.capability_id,
            now_epoch=int(timestamp.timestamp()),
            session_id=request.session_id,
            path=path,
            hard_risk=hard_risk,
            consume=False,
        )

        # 5. trust policy over the composed action.
        action = self._build_action(request, args, record, risk, assessment.tainted, assessment.taint_sensitive, envelope, network_host)
        policy = self._policy.evaluate(action, approval_bound=False, undo_proven=False)
        decision, reason = policy.decision, policy.reason

        # envelope tier overlay: ask_first/always_ask floor the policy verdict;
        # an in-envelope grant used OUTSIDE its compiled scope is an
        # escalation and parks for diff-approval (never grant-downgradable).
        downgradable = True
        if envelope is not None:
            tier_grant = envelope.grant_for(request.capability_id)
            if tier_grant is None:
                if record.side_effect is not SideEffectClass.none:
                    # GAP-4: a CHILD principal can never widen its parent's
                    # envelope — out-of-envelope for a subagent is DENY, while
                    # the coordinator itself may still escalate via ASK.
                    if request.context.parent_principal_id is not None:
                        return self._finalize(
                            request, args, TrustDecision.DENY, "child_out_of_envelope",
                            envelope=envelope, record=record,
                        )
                    decision, reason = TrustDecision.ASK, "capability_not_in_envelope"
            elif (
                scope_violation := _scope_violation(tier_grant, path=path, network_host=network_host)
            ) is not None:
                decision, reason, downgradable = TrustDecision.ASK, scope_violation, False
            elif tier_grant.tier is GrantTier.always_ask:
                decision, reason, downgradable = TrustDecision.ASK, "tier_always_ask", False
            elif tier_grant.tier is GrantTier.ask_first and decision is TrustDecision.AUTO:
                decision, reason = TrustDecision.ASK, "tier_ask_first"
        elif record.side_effect is not SideEffectClass.none and decision is TrustDecision.AUTO:
            # no objective opened: side effects do not run silently.
            decision, reason = TrustDecision.ASK, "no_envelope_for_side_effect"

        if assessment.forced_decision is TrustDecision.ASK and decision is not TrustDecision.DENY:
            decision, reason, downgradable = TrustDecision.ASK, assessment.reasons[0], False

        # 6. pre-call governors (budget DENY; deadman/novelty/rate/loop ASK).
        verdict = self.governors.precall(
            capability_id=request.capability_id,
            requested_units=request.requested_units,
            run_id=request.run_id,
            objective_id=request.context.objective_id,
            state_hash=request.context.state_hash,
            network_host=network_host,
            recipient=_text_or_none(args.get("recipient")),
            side_effecting=record.side_effect is not SideEffectClass.none,
            now=timestamp,
        )
        if not verdict.allowed and verdict.forced_decision is not None:
            forced = verdict.forced_decision
            if forced is TrustDecision.DENY or decision is not TrustDecision.DENY:
                decision, reason, downgradable = forced, verdict.reason, False

        # 6.5 explainability gate. A side-effecting action Zeus cannot describe
        # in a vetted plain-language card must never resolve to AUTO/NOTIFY —
        # not on an envelope auto-tier (escalated here) and not via a standing
        # license (guarded in 4b below, so the grant is never burned for it).
        # Enforced inside decide() so the receipt is the truth of the final
        # action, never a post-hoc gate mutation. Read-class capabilities are
        # always explainable → no ask-storm.
        explainable = (
            self._explainability is None
            or record.side_effect is SideEffectClass.none
            or self._explainability(record)
        )
        if decision in {TrustDecision.AUTO, TrustDecision.NOTIFY} and not explainable:
            decision, reason, downgradable = (
                TrustDecision.ASK,
                "no_plain_language_template",
                False,
            )

        # 4b. license downgrade: a covering grant turns a soft ASK into AUTO —
        # but only for an explainable action. An unexplained consequence card
        # can't be silently licensed away (and the grant is left unconsumed).
        if (
            decision is TrustDecision.ASK
            and downgradable
            and grant is not None
            and not hard_risk
            and explainable
        ):
            decision, reason = TrustDecision.AUTO, "covered_by_grant_{0}".format(grant.scope.value)
            if not _forward_once_grant_to_owner(request, record, grant.scope):
                self.grants.consume(grant.grant_id)

        if decision is TrustDecision.ASK and self.replay_authorizations is not None:
            replay = self.replay_authorizations.consume(
                host=request.context.host.value,
                session_id=request.session_id,
                capability_id=request.capability_id,
                payload_hash=replay_payload_hash(args),
                now=timestamp,
            )
            if replay is not None:
                decision, reason = TrustDecision.AUTO, "covered_by_replay_once"

        # D9: another gate owns the synchronous ask on this surface (a paired
        # blocking hook). Downgrade a SOFT ask to NOTIFY so the operator is
        # asked once at that gate, not twice. Walls (DENY) are never deferred.
        if (
            request.context.defer_ask_to_owner
            and decision is TrustDecision.ASK
            and downgradable
            and not hard_risk
            and explainable
            and record.side_effect is SideEffectClass.none
        ):
            decision, reason = TrustDecision.NOTIFY, "{0}_deferred_to_owner".format(reason)

        # advance the loop governor only for a RELEASED decision (D4): a parked
        # ASK the host keeps retrying must not spin the iteration counter.
        if decision in {TrustDecision.AUTO, TrustDecision.NOTIFY}:
            self.governors.record_release(
                run_id=request.run_id, state_hash=request.context.state_hash
            )

        return self._finalize(
            request, args, decision, reason,
            envelope=envelope, record=record, action=action, record_known=record_known,
        )

    # ------------------------------------------------------------------ record
    def record(
        self,
        receipt_id: str,
        outcome: ExecutionOutcome,
        *,
        run_id: Optional[str] = None,
        capability_id: Optional[str] = None,
        session_id: Optional[str] = None,
        objective_id: Optional[str] = None,
    ) -> str:
        """Bind the host's execution outcome to its decision receipt.

        Returns the ledger record id of the outcome. Feeds budget spend,
        earned-trust counts, and session taint. Explicit keyword hints win over
        the receipt payload — ledger payloads are redacted on append, so a
        capability id that itself looks secret-like (e.g. ``credential.*``
        variants) survives only via the caller's hint.
        """
        decision_record = self._decision_record(receipt_id)
        payload = _payload_of(decision_record) if decision_record is not None else {}
        bound_run_id = run_id or (str(decision_record["run_id"]) if decision_record else "run.unbound")
        event = self.recorder.record_outcome(
            run_id=bound_run_id,
            outcome=outcome,
            caused_by=(receipt_id,),
        )
        capability_id = capability_id or _text_or_none(payload.get("capability_id"))
        session_id = session_id or _text_or_none(payload.get("session_id"))
        objective_id = objective_id or _text_or_none(payload.get("objective_id"))
        if outcome.cost_actual_units > 0:
            from zeus_agent.governor_runtime import BudgetScope

            self.governors.budget.charge(BudgetScope.run, bound_run_id, outcome.cost_actual_units)
            if objective_id is not None:
                self.governors.budget.charge(BudgetScope.objective, objective_id, outcome.cost_actual_units)
            self.governors.budget.charge(BudgetScope.fleet, "fleet", outcome.cost_actual_units)
        if capability_id is not None and self.trust_stats is not None:
            success, failure = self.trust_stats.get(capability_id) or (0, 0)
            if outcome.status is ExecutionStatus.success:
                success += 1
            else:
                failure += 1
            self.trust_stats.upsert(capability_id, success_count=success, failure_count=failure)
        if capability_id is not None and session_id is not None and outcome.status is ExecutionStatus.success:
            self.taint.observe_capability(
                session_id, capability_id, record=self.capabilities.get(capability_id)
            )
        return event.record_id

    # ------------------------------------------------------------------ internals
    def _build_action(
        self,
        request: DecisionRequest,
        args: dict[str, JsonValue],
        record: CapabilityRecord,
        risk: ActionRisk,
        tainted: bool,
        taint_sensitive: bool,
        envelope: Optional[AuthorityEnvelope],
        network_host: Optional[str],
    ) -> TrustLoopAction:
        max_units = envelope.budget_per_run_units if envelope is not None and envelope.budget_per_run_units > 0 else 1_000_000
        if self._seq_counter is not None:
            seq = self._seq_counter()
        else:
            self._decision_seq += 1
            seq = self._decision_seq
        return TrustLoopAction(
            action_id="decision.{0}.{1:04d}".format(request.run_id.replace(".", "_"), seq),
            run_id=request.run_id,
            goal_contract_id=request.context.objective_id or "adhoc.objective",
            criterion_id="decision-api.v1",
            capability_id=request.capability_id,
            payload=args,
            risk=risk,
            reversibility=record.reversibility,
            tainted=tainted,
            taint_sensitive=taint_sensitive,
            budget=BudgetEnvelope(
                max_units=max_units,
                requested_units=min(request.requested_units, max_units),
            ),
            credential_scope=_text_or_none(args.get("credential_scope")),
            network_host=network_host,
            live_network=network_host is not None,
        )

    def _finalize(
        self,
        request: DecisionRequest,
        args: dict[str, JsonValue],
        decision: TrustDecision,
        reason: str,
        *,
        envelope: Optional[AuthorityEnvelope],
        record: CapabilityRecord,
        action: Optional[TrustLoopAction] = None,
        record_known: bool = True,
    ) -> DecisionResponse:
        obligations = self._obligations(decision, record)
        if not record_known:
            reason = "{0}.unregistered_conservative".format(reason)
        payload = {
            "principal_id": request.principal_id,
            "session_id": request.session_id,
            "capability_id": request.capability_id,
            "host": request.context.host.value,
            "surface": request.context.surface.value,
            "objective_id": request.context.objective_id,
            "decision": decision.value,
            "reason": reason,
            "requested_units": request.requested_units,
            "obligations": [item.value for item in obligations],
            "args": args,
        }
        if action is not None:
            payload["action_id"] = action.action_id
            payload["action_payload_hash"] = replay_payload_hash(args)
        event = self.recorder.record_decision(run_id=request.run_id, payload=payload)
        parked_action_id: Optional[str] = None
        if decision is TrustDecision.ASK and action is not None:
            parked_action_id = self.queue.park(
                action,
                host=request.context.host.value,
                session_id=request.session_id,
                payload_hash=replay_payload_hash(args),
            ).parked_action_id
        return DecisionResponse(
            decision=decision,
            reason=reason,
            receipt_id=event.record_id,
            obligations=obligations,
            parked_action_id=parked_action_id,
            envelope_ref=envelope.envelope_id if envelope is not None else None,
            ttl_ms=_AUTO_TTL_MS if decision is TrustDecision.AUTO else 0,
        )

    def _obligations(self, decision: TrustDecision, record: CapabilityRecord) -> tuple[Obligation, ...]:
        obligations: list[Obligation] = []
        if record.side_effect is not SideEffectClass.none and decision is not TrustDecision.DENY:
            obligations.append(Obligation.require_evidence)
        if (
            decision is not TrustDecision.DENY
            and record.reversibility is not Reversibility.reversible
            and record.side_effect in {SideEffectClass.account_write, SideEffectClass.public_write}
        ):
            obligations.append(Obligation.require_undo_plan)
        if is_private_source(record.capability_id):
            obligations.append(Obligation.redact_response)
        if decision is TrustDecision.NOTIFY:
            obligations.append(Obligation.notify_digest)
        return tuple(obligations)

    def _decision_record(self, receipt_id: str) -> Optional[dict[str, JsonValue]]:
        return self.recorder.ledger.record_by_id(receipt_id)


def _scope_violation(
    grant: GrantedCapability,
    *,
    path: Optional[str],
    network_host: Optional[str],
) -> Optional[str]:
    """Is the concrete action outside the scope the compiler granted?"""
    if grant.path_scopes and path is not None:
        inside = any(
            path == scope or path.startswith(scope.rstrip("/") + "/")
            for scope in grant.path_scopes
        )
        if not inside:
            return "path_outside_envelope_scope"
    if grant.network_hosts and network_host is not None:
        if network_host not in set(grant.network_hosts):
            return "host_outside_envelope_scope"
    return None


def _forward_once_grant_to_owner(
    request: DecisionRequest,
    record: CapabilityRecord,
    scope: GrantScope,
) -> bool:
    return (
        request.context.defer_ask_to_owner
        and request.context.surface.value == "llm_proxy"
        and record.side_effect is not SideEffectClass.none
        and scope is GrantScope.once
    )


def _redact_args(args: dict[str, JsonValue]) -> dict[str, JsonValue]:
    redacted = _redact_json(dict(args))
    return redacted if isinstance(redacted, dict) else {}


def _text_or_none(value: JsonValue | None) -> Optional[str]:
    if isinstance(value, str) and value.strip() != "":
        return value.strip()
    return None


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
