"""Zeus agent session loop."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from zeus_agent.agent.background_review import review_run_for_skill_updates
from zeus_agent.agent.context import build_run_context
from zeus_agent.core.mneme import record_evidence
from zeus_agent.schemas.agent import AgentMessage, AgentSessionReport, ToolCallRequest, ToolCallResult
from zeus_agent.storage.artifacts import persist_json_artifact
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore
from zeus_agent.tools.registry import ToolContext, ToolRegistry, default_tool_registry


class ZeusAgentSession:
    """A small but real agent loop around Zeus tools.

    The model transport is deliberately absent in this first absorption pass.
    Instead, callers can provide tool calls, and the session guarantees that
    every call is governed, persisted, and evidence-backed.
    """

    def __init__(
        self,
        run_id: str,
        *,
        home: Path | None = None,
        session_id: str | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.run_id = run_id
        self.home = home
        self.session_id = session_id or f"session_{uuid4().hex}"
        self.registry = registry or default_tool_registry()
        self.store = RunStore(home)
        self.state = StateStore(self.store.home)

    def start(self) -> None:
        contract = self.store.load_goal_contract(self.run_id)
        self.state.upsert_session(
            self.session_id,
            run_id=self.run_id,
            title=contract.normalized_goal,
            status="active",
        )
        self.append_message(
            "system",
            "Zeus session started. GoalContract and Mneme evidence are the source of truth.",
        )

    def append_message(self, role: str, content: str) -> AgentMessage:
        message = AgentMessage(
            session_id=self.session_id,
            run_id=self.run_id,
            role=role,  # type: ignore[arg-type]
            content=content,
        )
        self.state.append_message(message)
        return message

    def run_tool_calls(self, calls: list[ToolCallRequest]) -> AgentSessionReport:
        self.start()
        contract = self.store.load_goal_contract(self.run_id)
        context = ToolContext(
            run_id=self.run_id,
            home=self.store.home,
            session_id=self.session_id,
            approved=contract.approval_state == "approved",
        )
        results: list[ToolCallResult] = []
        for call in calls:
            self.append_message("assistant", f"Tool request: {call.name} - {call.reason}")
            result = self.registry.execute(context, call)
            results.append(result)
            self.append_message("tool", f"{result.name}: {result.status} - {result.summary}")

        status = "completed"
        if any(result.status == "blocked" for result in results):
            status = "blocked"
        elif any(result.status == "failed" for result in results):
            status = "escalated"
        report = AgentSessionReport(
            session_id=self.session_id,
            run_id=self.run_id,
            status=status,
            tool_results=results,
            notes=["All tool calls were routed through Zeus ToolRegistry."],
        )
        artifact = persist_json_artifact(
            self.run_id,
            "agent_session",
            f"{report.report_id}.json",
            report.model_dump(mode="json"),
            home=self.store.home,
        )
        record_evidence(
            self.run_id,
            "verification",
            f"Agent session {report.session_id} finished with {report.status}.",
            passed=status == "completed",
            artifact_paths=[str(artifact)],
            payload={"tool_count": len(results), "status": status},
            home=self.store.home,
        )
        review_run_for_skill_updates(self.run_id, home=self.store.home)
        return report

    def run_control_cycle(self) -> AgentSessionReport:
        context = build_run_context(self.run_id, home=self.store.home)
        self.append_message("user", f"Approved run context: {context['goal']}")
        calls = [
            ToolCallRequest(
                name="zeus.record_note",
                arguments={"summary": "Loaded approved run context.", "note": str(context)},
                reason="Anchor session to GoalContract.",
                requires_approval=False,
            ),
            ToolCallRequest(
                name="zeus.checkpoint",
                arguments={},
                reason="Capture restorable baseline before implementation.",
            ),
            ToolCallRequest(
                name="zeus.diff_gate",
                arguments={},
                reason="Observe current workspace state.",
                requires_approval=False,
            ),
        ]
        report = self.run_tool_calls(calls)
        if report.status == "completed":
            record_evidence(
                self.run_id,
                "note",
                "Zeus control cycle completed; no model-generated implementation plan was supplied yet.",
                passed=False,
                payload={"next_required": "Attach model planner or scripted tool plan."},
                home=self.store.home,
            )
        return report

