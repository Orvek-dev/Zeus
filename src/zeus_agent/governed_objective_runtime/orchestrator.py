from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Final, Optional

from pydantic import JsonValue

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.objective_card_runtime import ObjectiveFrameInput, compile_from_frame
from zeus_agent.objective_card_runtime.models import ObjectiveCard
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustLedger,
    SQLiteTrustStatStore,
)
from zeus_agent.workflow_execution_runtime import (
    RunState,
    WorkflowExecutionRuntime,
    WorkflowExecutionStateStore,
)
from zeus_agent.workflow_fabric_runtime import NodeKind, WorkflowCandidate

from .models import GovernedObjectiveResult

Handler = Callable[[dict[str, JsonValue]], dict[str, JsonValue]]
_EVIDENCE_TARGET: Final = "mneme.workflow_execution"
_PRINCIPAL: Final = "operator.local"

_SIDE_EFFECT_TO_KERNEL: Final = {
    SideEffectClass.none: (),
    SideEffectClass.local_write: (SideEffect.filesystem_write,),
    SideEffectClass.account_write: (SideEffect.network,),
    SideEffectClass.public_write: (SideEffect.network,),
}
_SIDE_EFFECT_TO_RISK: Final = {
    SideEffectClass.none: CapabilityRisk.low,
    SideEffectClass.local_write: CapabilityRisk.medium,
    SideEffectClass.account_write: CapabilityRisk.high,
    SideEffectClass.public_write: CapabilityRisk.high,
}


class GovernedObjectiveOrchestrator:
    """The assembled spine: frame → card → (if ready) executor → evidence.

    Builds the lease, dispatcher, and approvals from the compiled card so callers
    (CLI / ZeusAgent) get one method that runs the whole governed path. Handlers
    for capability nodes are injected (provider/MCP/sandbox); a deterministic fake
    handler is the default so the path runs end-to-end without network.
    """

    def __init__(self, *, home: Path, handlers: Optional[dict[str, Handler]] = None) -> None:
        self._home = home
        self._handlers = dict(handlers or {})
        self._ledger = SQLiteEvidenceLedger(home / "trust" / "evidence.sqlite3")
        self._store = WorkflowExecutionStateStore(home / "runs" / "workflow.sqlite3")
        self._trust = TrustLedger(store=SQLiteTrustStatStore(home / "trust" / "stats.sqlite3"))

    def compile_and_run(
        self,
        frame: ObjectiveFrameInput,
        *,
        run_id: Optional[str] = None,
    ) -> GovernedObjectiveResult:
        card = compile_from_frame(frame)
        if card.decision != "ready_to_start":
            # Not startable: hand back the card (questions / gaps / over-budget /
            # secret-blocked) without executing anything.
            return _from_card(card, stage="compiled")

        candidate = _chosen_candidate(card, frame)
        if candidate is None:
            return _from_card(card, stage="blocked")
        resolved_run_id = run_id or _run_id(card.normalized_objective)
        lease = self._lease(card, candidate, resolved_run_id)
        runtime = self._runtime(candidate)
        run = runtime.start(
            candidate, lease=lease, objective_id=resolved_run_id,
            required_criteria=card.decision_record.verdicts[0].covered_criteria
            if card.decision_record.verdicts else (),
        )
        return _from_card(card, stage=run.status.value, run=run,
                          evidence=len(self._ledger.records()))

    def resume(
        self,
        run_id: str,
        *,
        approved_gates: tuple[str, ...],
    ) -> GovernedObjectiveResult:
        stored = self._store.load(run_id)
        if stored is None:
            raise ValueError("unknown_run:{0}".format(run_id))
        candidate = WorkflowCandidate.model_validate_json(stored.candidate_json)
        lease = self._lease_for_run(stored, candidate)
        runtime = self._runtime(candidate)
        approvals = self._capability_approvals(stored.run_id, stored.objective_id, candidate)
        run = runtime.resume(
            run_id, lease=lease, approved_gates=approved_gates, capability_approvals=approvals
        )
        card_payload: dict[str, JsonValue] = {"normalized_objective": stored.objective_id}
        return GovernedObjectiveResult(
            stage=run.status.value, run_id=run.run_id, card=card_payload,
            run=run.model_dump(mode="json"), evidence_record_count=len(self._ledger.records()),
        )

    def evidence_timeline(self, run_id: str) -> list[dict[str, JsonValue]]:
        """The ordered, causal record of a run — "what was done and what proves
        completion". The user-facing answer to 'why did this run this way?'."""
        timeline: list[dict[str, JsonValue]] = []
        for record in self._ledger.records():
            if record["run_id"] != run_id:
                continue
            payload = json.loads(str(record["payload_json"]))
            timeline.append(
                {
                    "seq": record["seq"],
                    "record_id": record["record_id"],
                    "kind": record["kind"],
                    "node_id": payload.get("node_id"),
                    "status": payload.get("status") or payload.get("decision"),
                    "caused_by": payload.get("caused_by", []),
                }
            )
        return timeline

    # -- internals -----------------------------------------------------------

    def _runtime(self, candidate: WorkflowCandidate) -> WorkflowExecutionRuntime:
        graph, handlers = self._graph_and_handlers(candidate)
        dispatcher = GovernedExecutionDispatcher(
            capability_graph=graph, handlers=handlers, ledger=self._ledger
        )
        return WorkflowExecutionRuntime(
            dispatcher=dispatcher, ledger=self._ledger, state_store=self._store,
            trust_ledger=self._trust,
        )

    def _graph_and_handlers(self, candidate: WorkflowCandidate):
        descriptors = []
        handlers: dict[str, Handler] = {}
        for node in candidate.nodes:
            if node.kind is not NodeKind.capability or node.capability_ref is None:
                continue
            descriptors.append(
                CapabilityDescriptor(
                    capability_id=node.capability_ref,
                    name=node.capability_ref.replace(".", "_"),
                    risk=_SIDE_EFFECT_TO_RISK[node.side_effect],
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    side_effects=list(_SIDE_EFFECT_TO_KERNEL[node.side_effect]),
                )
            )
            handlers[node.capability_ref] = self._handlers.get(node.capability_ref, _fake_handler)
        if not descriptors:
            descriptors.append(
                CapabilityDescriptor(
                    capability_id="provider.fake.generate", name="provider_fake_generate",
                    risk=CapabilityRisk.low, input_schema={"type": "object"},
                    output_schema={"type": "object"},
                )
            )
            handlers["provider.fake.generate"] = _fake_handler
        return CapabilityGraph(tuple(descriptors)), handlers

    def _lease(self, card: ObjectiveCard, candidate: WorkflowCandidate, run_id: str) -> RuntimeLease:
        caps = tuple(
            n.capability_ref for n in candidate.nodes
            if n.kind is NodeKind.capability and n.capability_ref is not None
        ) or ("provider.fake.generate",)
        hosts = tuple({n.network_host for n in candidate.nodes if n.network_host} )
        scopes = tuple({n.credential_scope for n in candidate.nodes if n.credential_scope})
        now = datetime.now(timezone.utc)
        return RuntimeLease(
            lease_id="{0}.lease".format(run_id), objective_id=run_id, principal_id=_PRINCIPAL,
            run_id=run_id, allowed_capabilities=caps, credential_scopes=scopes,
            network_hosts=hosts, budget_limit=max(card.cost.per_run_units, 1),
            evidence_target=_EVIDENCE_TARGET, live_transport_allowed=True,
            issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(minutes=30),
        )

    def _lease_for_run(self, run: RunState, candidate: WorkflowCandidate) -> RuntimeLease:
        caps = tuple(
            n.capability_ref for n in candidate.nodes
            if n.kind is NodeKind.capability and n.capability_ref is not None
        ) or ("provider.fake.generate",)
        hosts = tuple({n.network_host for n in candidate.nodes if n.network_host})
        scopes = tuple({n.credential_scope for n in candidate.nodes if n.credential_scope})
        now = datetime.now(timezone.utc)
        return RuntimeLease(
            lease_id="{0}.lease".format(run.run_id), objective_id=run.objective_id,
            principal_id=_PRINCIPAL, run_id=run.run_id, allowed_capabilities=caps,
            credential_scopes=scopes, network_hosts=hosts, budget_limit=max(run.budget_limit, 1),
            evidence_target=_EVIDENCE_TARGET, live_transport_allowed=True,
            issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(minutes=30),
        )

    def _capability_approvals(self, run_id: str, objective_id: str, candidate: WorkflowCandidate):
        approvals = {}
        for node in candidate.nodes:
            if node.kind is not NodeKind.capability or node.capability_ref is None:
                continue
            if node.side_effect is SideEffectClass.none:
                continue
            cap = node.capability_ref
            approval = ApprovalReceipt(
                principal_id=_PRINCIPAL, run_id=run_id, goal_contract_id=objective_id,
                approved_capabilities=[cap], nonce="{0}.optin".format(cap),
            )
            envelope = ApprovalEnvelope(
                envelope_id="{0}.env".format(cap), capability_id=cap,
                approval_receipt_id="{0}.optin".format(cap),
                predicted_effects=("execute node {0}".format(node.node_id),),
                reversibility=Reversibility.irreversible, risk=ActionRisk.high,
                budget=BudgetEnvelope(max_units=max(node.cost_units, 1), requested_units=max(node.cost_units, 1)),
            )
            approvals[cap] = (approval, envelope)
        return approvals


def _fake_handler(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {"node": payload.get("node_id"), "ok": True}


def _chosen_candidate(card: ObjectiveCard, frame: ObjectiveFrameInput) -> Optional[WorkflowCandidate]:
    for candidate in frame.candidates:
        if candidate.candidate_id == card.chosen_workflow_id:
            return candidate
    return None


def _run_id(objective: str) -> str:
    digest = hashlib.sha256(objective.encode("utf-8")).hexdigest()[:12]
    return "objrun.{0}".format(digest)


def _from_card(
    card: ObjectiveCard,
    *,
    stage: str,
    run: Optional[RunState] = None,
    evidence: int = 0,
) -> GovernedObjectiveResult:
    return GovernedObjectiveResult(
        stage=stage,
        run_id=run.run_id if run is not None else None,
        card=card.to_payload(),
        run=run.model_dump(mode="json") if run is not None else None,
        questions=card.questions,
        capability_gaps=card.capability_gaps,
        evidence_record_count=evidence,
    )
