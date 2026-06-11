from __future__ import annotations

import hashlib
import json
from typing import Callable, Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
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
    ZeusDecisionEngine,
)
from zeus_agent.security.credentials import contains_secret_material
from zeus_agent.taint_runtime import SessionTaintTracker, TaintLabel
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    Reversibility,
    SQLiteControlPlaneStore,
    TrustDecision,
)

from .scan import scan_for_injection

_RELEASED: Final = {TrustDecision.AUTO, TrustDecision.NOTIFY}
# Per-tool budgets are denominated in CALLS (1 unit per call): the simplest
# spend a human can reason about when licensing an MCP tool.
_UNITS_PER_CALL: Final = 1

ListTools = Callable[[], list[dict[str, JsonValue]]]
CallTool = Callable[[str, dict[str, JsonValue]], dict[str, JsonValue]]


class DownstreamServer(BaseModel):
    """One real MCP server behind the gateway (transport injected)."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str
    list_tools: ListTools
    call_tool: CallTool


class GatewaySession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    principal_id: str = "agent.mcp_client"
    session_id: str = "mcp-gateway.default"
    objective_id: Optional[str] = None
    host: HostKind = HostKind.console

    def run_id(self) -> str:
        cleaned = "".join(ch for ch in self.session_id if ch.isalnum())
        return "run.mcp.{0}".format((cleaned[:12] or "default").lower())


class McpCallOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    ok: bool
    result: Optional[dict[str, JsonValue]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    receipt_id: Optional[str] = None
    parked_action_id: Optional[str] = None
    injection_findings: tuple[str, ...] = ()
    secret_findings: int = 0


class SyncReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    imported: tuple[str, ...] = ()
    requarantined: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    injection_flagged: tuple[str, ...] = ()


class McpGateway:
    """Gate 2 — one MCP server to the host, a governed client to the rest.

    Every downstream tool imports QUARANTINED (fail-closed); de-quarantine is
    an explicit operator review; a changed schema hash re-quarantines
    (rug-pull defense); tool results are scanned and taint the session.
    """

    def __init__(
        self,
        *,
        engine: ZeusDecisionEngine,
        store: SQLiteControlPlaneStore,
        downstreams: tuple[DownstreamServer, ...] = (),
        expose_quarantined: bool = False,
        requarantine_on_result_injection: bool = True,
        persist_taint: Optional[Callable[[SessionTaintTracker, tuple[str, ...]], None]] = None,
    ) -> None:
        self.engine = engine
        self.store = store
        self.downstreams = {server.name: server for server in downstreams}
        self.expose_quarantined = expose_quarantined
        self.requarantine_on_result_injection = requarantine_on_result_injection
        self._persist_taint = persist_taint
        self._tool_defs: dict[str, dict[str, JsonValue]] = {}
        self._load_persisted()

    # ------------------------------------------------------------------- sync
    def sync_tools(self) -> SyncReport:
        imported: list[str] = []
        requarantined: list[str] = []
        unchanged: list[str] = []
        flagged: list[str] = []
        for server in self.downstreams.values():
            for tool in server.list_tools():
                name = str(tool.get("name", "")).strip()
                if not name:
                    continue
                capability_id = "mcp.{0}.{1}".format(server.name, name)
                schema_hash = _schema_hash(tool)
                description = str(tool.get("description", "") or "")
                existing = self._record(capability_id)
                if existing is None:
                    record = import_mcp_capability(
                        capability_id=capability_id,
                        title=name,
                        verb_class=VerbClass.transform,
                        input_summary=_summary(tool.get("inputSchema")),
                        output_summary="mcp tool result",
                        schema_hash=schema_hash,
                        server_ref=server.name,
                    )
                    imported.append(capability_id)
                else:
                    record = reconcile_schema(existing, schema_hash)
                    if record.status is CapabilityStatus.quarantined and existing.status is CapabilityStatus.active:
                        requarantined.append(capability_id)
                    elif record == existing:
                        unchanged.append(capability_id)
                injection = scan_for_injection(description)
                if injection:
                    flagged.append(capability_id)
                    record = record.model_copy(update={"status": CapabilityStatus.quarantined})
                self._save(record)
                self._tool_defs[capability_id] = dict(tool)
                self.store.kv_set("mcp.tooldef.{0}".format(capability_id), json.dumps(tool))
        report = SyncReport(
            imported=tuple(imported),
            requarantined=tuple(requarantined),
            unchanged=tuple(unchanged),
            injection_flagged=tuple(flagged),
        )
        if requarantined or flagged:
            self.engine.recorder.record_decision(
                run_id="run.mcp.sync",
                payload={
                    "capability_id": "mcp.gateway.sync",
                    "decision": "notify",
                    "reason": "requarantine_notice",
                    "requarantined": list(requarantined),
                    "injection_flagged": list(flagged),
                },
            )
        return report

    # ------------------------------------------------------------------ tools
    def tools_for_host(self) -> list[dict[str, JsonValue]]:
        """The host sees only de-quarantined tools (or all, risk-tagged)."""
        exposed: list[dict[str, JsonValue]] = []
        for capability_id, definition in sorted(self._tool_defs.items()):
            record = self._record(capability_id)
            if record is None:
                continue
            if record.status is CapabilityStatus.quarantined and not self.expose_quarantined:
                continue
            entry = dict(definition)
            entry["name"] = capability_id.replace(".", "__")  # MCP-safe alias
            if record.status is CapabilityStatus.quarantined:
                entry["description"] = "[QUARANTINED — zeus mcp --approve {0}] {1}".format(
                    capability_id, entry.get("description", "")
                )
            exposed.append(entry)
        return exposed

    def approve_tool(
        self,
        capability_id: str,
        *,
        principal_id: str = "operator.local",
        side_effect: Optional[SideEffectClass] = None,
        reversibility: Optional[Reversibility] = None,
    ) -> bool:
        """De-quarantine after explicit operator review — never automatic.

        Review is also CLASSIFICATION: the import was fail-closed
        (account-write, irreversible), so without an honest risk assignment a
        read-only tool would hard-ASK forever. The assignment is ledgered.
        """
        record = self._record(capability_id)
        if record is None:
            return False
        updates: dict[str, object] = {"status": CapabilityStatus.active}
        if side_effect is not None:
            updates["side_effect"] = side_effect
        if reversibility is not None:
            updates["reversibility"] = reversibility
        self._save(record.model_copy(update=updates))
        self.engine.recorder.record_decision(
            run_id="run.mcp.review",
            payload={
                "capability_id": "registry.dequarantine",
                "target": capability_id,
                "decision": "allow",
                "reason": "operator_review",
                "principal_id": principal_id,
                "assigned_side_effect": side_effect.value if side_effect else record.side_effect.value,
                "assigned_reversibility": (
                    reversibility.value if reversibility else record.reversibility.value
                ),
            },
        )
        return True

    # ------------------------------------------------------------------- call
    def call_tool(
        self,
        session: GatewaySession,
        capability_id: str,
        arguments: dict[str, JsonValue],
    ) -> McpCallOutcome:
        capability_id = capability_id.replace("__", ".") if "__" in capability_id else capability_id
        record = self._record(capability_id)
        server_name, tool_name = _split(capability_id)
        server = self.downstreams.get(server_name or "")
        if record is None or server is None:
            return McpCallOutcome(ok=False, error="unknown tool", error_code="unknown_tool")

        # per-tool budget (units = calls) — checked before the decision so an
        # exhausted tool never even consults policy.
        limit = self.store.budget_limit("capability", capability_id)
        if limit is not None:
            spent = self.store.budget_spent("capability", capability_id)
            if spent + _UNITS_PER_CALL > limit:
                event = self.engine.recorder.record_decision(
                    run_id=session.run_id(),
                    payload={
                        "principal_id": session.principal_id,
                        "session_id": session.session_id,
                        "capability_id": capability_id,
                        "surface": GateSurface.mcp_gateway.value,
                        "decision": "deny",
                        "reason": "budget_exhausted_capability",
                    },
                )
                return McpCallOutcome(
                    ok=False,
                    error="[Zeus] denied: budget_exhausted_capability",
                    error_code="budget_exhausted_capability",
                    receipt_id=event.record_id,
                )

        request = DecisionRequest(
            principal_id=session.principal_id,
            session_id=session.session_id,
            run_id=session.run_id(),
            capability_id=capability_id,
            args=dict(arguments),
            requested_units=_UNITS_PER_CALL,
            context=DecisionContext(
                host=session.host,
                surface=GateSurface.mcp_gateway,
                objective_id=session.objective_id,
            ),
        )
        response = self.engine.decide(request)
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id,
            host=session.host.value,
            surface=GateSurface.mcp_gateway.value,
            capability_id=capability_id,
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        if response.decision is TrustDecision.DENY:
            return McpCallOutcome(
                ok=False,
                error="[Zeus] denied: {0}".format(response.reason),
                error_code=response.reason,
                receipt_id=response.receipt_id,
            )
        if response.decision is TrustDecision.ASK:
            return McpCallOutcome(
                ok=False,
                error=(
                    "[Zeus] approval required: {0} (parked: {1}); "
                    "re-issue after the operator approves".format(
                        response.reason, response.parked_action_id
                    )
                ),
                error_code="approval_required",
                receipt_id=response.receipt_id,
                parked_action_id=response.parked_action_id,
            )

        try:
            result = server.call_tool(tool_name, arguments)
        except Exception as exc:  # downstream failure is evidence, not silence
            self.engine.record(
                response.receipt_id,
                ExecutionOutcome(status=ExecutionStatus.error, notes="downstream: {0}".format(exc)),
                capability_id=capability_id,
                session_id=session.session_id,
            )
            return McpCallOutcome(
                ok=False,
                error="[Zeus] downstream error: {0}".format(exc),
                error_code="downstream_error",
                receipt_id=response.receipt_id,
            )

        result_text = _result_text(result)
        injection = scan_for_injection(result_text)
        secret_findings = 1 if contains_secret_material(result_text) else 0
        if injection:
            # a poisoned result taints the whole session (untrusted) and can
            # drop the tool straight back into quarantine.
            self.engine.taint.stamp(
                session.session_id, TaintLabel.untrusted, "mcp_injection:{0}".format(capability_id)
            )
            if self._persist_taint is not None:
                self._persist_taint(self.engine.taint, (session.session_id,))
            if self.requarantine_on_result_injection:
                fresh = self._record(capability_id)
                if fresh is not None:
                    self._save(fresh.model_copy(update={"status": CapabilityStatus.quarantined}))
        self.store.add_budget_spend("capability", capability_id, _UNITS_PER_CALL)
        self.engine.record(
            response.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                cost_actual_units=_UNITS_PER_CALL,
                notes="mcp_gateway {0}".format(capability_id),
            ),
            capability_id=capability_id,
            session_id=session.session_id,
            objective_id=session.objective_id,
        )
        return McpCallOutcome(
            ok=True,
            result=result,
            receipt_id=response.receipt_id,
            injection_findings=injection,
            secret_findings=secret_findings,
        )

    # -------------------------------------------------------------- internals
    def _record(self, capability_id: str) -> Optional[CapabilityRecord]:
        raw = self.store.capability_get(capability_id)
        if raw is None:
            return None
        try:
            return CapabilityRecord.model_validate_json(raw)
        except ValueError:
            return None

    def _save(self, record: CapabilityRecord) -> None:
        self.store.capability_save(record.capability_id, record.model_dump_json())
        self.engine.capabilities.register(record)

    def _load_persisted(self) -> None:
        for capability_id, raw in self.store.capability_all():
            if not capability_id.startswith("mcp."):
                continue
            try:
                record = CapabilityRecord.model_validate_json(raw)
            except ValueError:
                continue
            self.engine.capabilities.register(record)
            tooldef_raw = self.store.kv_get("mcp.tooldef.{0}".format(capability_id))
            if tooldef_raw is not None:
                try:
                    parsed = json.loads(tooldef_raw)
                except ValueError:
                    parsed = None
                if isinstance(parsed, dict):
                    self._tool_defs[capability_id] = parsed


def _schema_hash(tool: dict[str, JsonValue]) -> str:
    material = json.dumps(
        {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "inputSchema": tool.get("inputSchema"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _summary(schema: JsonValue | None) -> str:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict) and properties:
            return "args: {0}".format(", ".join(sorted(properties)[:8]))
    return "mcp tool input"


def _split(capability_id: str) -> tuple[Optional[str], str]:
    parts = capability_id.split(".")
    if len(parts) >= 3 and parts[0] == "mcp":
        return parts[1], ".".join(parts[2:])
    return None, capability_id


def _result_text(result: dict[str, JsonValue]) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)[:1_000_000]
    except (TypeError, ValueError):
        return str(result)[:1_000_000]
