from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from zeus_agent.agent_runtime.live_loop_support import (
    CAPABILITY_ID,
    audit_summary,
    deny_audit_summary,
    stream_evidence,
)
from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.model_runtime.interfaces import ProviderRuntimeResponse
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.state.sqlite_store import SQLiteStateStore


class LiveAgentLoopPersistence:
    def __init__(self, home: Path) -> None:
        self._home = home

    def persist_session(
        self,
        *,
        message: str,
        first_turn: ProviderRuntimeResponse,
        tool_result_json: str,
        tool_evidence: MnemeEvidenceRecord,
        final_turn: ProviderRuntimeResponse,
    ) -> tuple[int, bool, int, bool]:
        store = SQLiteStateStore(self._home / "wave15-state.sqlite3")
        before = store.counts()
        suffix = uuid4().hex
        session_id = "wave15.session.{0}".format(suffix)
        first_turn_id = "wave15.turn.provider.{0}".format(suffix)
        tool_evidence_id = "wave15.evidence.tool.{0}".format(suffix)
        stream_evidence_id = "wave15.evidence.stream.{0}".format(suffix)
        store.create_session(session_id, "wave15.run.tool", "wave15.objective.liveagent")
        store.add_model_turn("wave15.turn.user.{0}".format(suffix), session_id, "user", message)
        store.add_model_turn(first_turn_id, session_id, "assistant", first_turn.content)
        store.add_evidence(stream_evidence_id, stream_evidence())
        store.add_evidence(tool_evidence_id, tool_evidence)
        store.add_tool_call(
            first_turn.tool_calls[0].call_id,
            first_turn_id,
            CAPABILITY_ID,
            {"text": message},
            "allowed",
            True,
            tool_evidence_id,
        )
        store.add_audit_event(
            "wave15.audit.dispatch.{0}".format(suffix),
            audit_summary(
                message=message,
                provider_id=first_turn.provider_id,
                model_id=first_turn.model_id,
                tool_call_id=first_turn.tool_calls[0].call_id,
                tool_name=first_turn.tool_calls[0].tool_name,
            ),
        )
        store.add_acceptance_link("REQ-ZEUS-WAVE15-001:S1", stream_evidence_id, "pass")
        store.add_acceptance_link("REQ-ZEUS-WAVE15-001:S2", tool_evidence_id, "pass")
        store.add_model_turn(
            "wave15.turn.tool.{0}".format(suffix),
            session_id,
            "tool",
            redact_secret_spans(tool_result_json),
        )
        store.add_model_turn("wave15.turn.final.{0}".format(suffix), session_id, "assistant", final_turn.content)
        after = store.counts()
        audit_delta = after.audit_events - before.audit_events
        return (
            after.evidence_records - before.evidence_records,
            after.sessions > before.sessions,
            audit_delta,
            audit_delta >= 1,
        )

    def persist_deny_audit(
        self,
        *,
        reason: str,
        message: str,
        network_opened: bool,
        handler_executed: bool = False,
    ) -> int:
        store = SQLiteStateStore(self._home / "wave15-state.sqlite3")
        before = store.counts()
        store.add_audit_event(
            "wave15.audit.deny.{0}".format(uuid4().hex),
            deny_audit_summary(
                reason=reason,
                message=message,
                network_opened=network_opened,
                handler_executed=handler_executed,
            ),
        )
        return store.counts().audit_events - before.audit_events

    def persist_policy_audit(self, *, reason: str, message: str = "") -> int:
        return self.persist_deny_audit(
            reason=reason,
            message=message,
            network_opened=False,
        )

    def audit_event_count(self) -> int:
        return SQLiteStateStore(self._home / "wave15-state.sqlite3").counts().audit_events
