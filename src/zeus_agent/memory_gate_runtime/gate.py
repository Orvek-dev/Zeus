from __future__ import annotations

import hashlib
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.mcp_gateway_runtime import scan_for_injection
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.taint_runtime import TaintLabel
from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore, TrustDecision

_KV_PREFIX: Final = "memory.cand."


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    candidate_id: str
    content: str  # redacted body; "" for a poisoned (never-promotable) candidate
    content_hash: str  # sha256 of the ORIGINAL content — a handle, not the text
    preview: str = ""  # redacted first-120-chars, kept only for poisoned candidates
    provenance: str
    session_id: str
    tainted: bool
    injection_findings: tuple[str, ...] = ()
    status: str = "candidate"  # candidate | promoted | rejected
    receipt_id: Optional[str] = None


class MemoryWriteGate:
    """Long-term memory writes land as CANDIDATES; only promotion makes them
    durable, and promotion is an operator review the ledger remembers."""

    def __init__(self, *, engine: ZeusDecisionEngine, store: SQLiteControlPlaneStore) -> None:
        self.engine = engine
        self.store = store

    # ------------------------------------------------------------------ write
    def propose(
        self,
        *,
        session_id: str,
        content: str,
        provenance: str,
        host: HostKind = HostKind.console,
    ) -> MemoryCandidate:
        tainted = TaintLabel.untrusted in self.engine.taint.labels(session_id)
        findings = scan_for_injection(content)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        response = self.engine.decide(
            DecisionRequest(
                principal_id="agent.memory",
                session_id=session_id,
                run_id="run.memory.gate",
                capability_id="memory.write",
                args={
                    "provenance": provenance,
                    "content_chars": len(content),
                    "tainted": tainted,
                },
                context=DecisionContext(host=host, surface=GateSurface.hook),
            )
        )

        # decision-respecting: a DENY stores NOTHING. The refusal is the
        # evidence; the raw content never lands in the KV at all. (No counter
        # is consumed, so stored candidate ids stay contiguous.)
        if response.decision is TrustDecision.DENY:
            return MemoryCandidate(
                candidate_id="mem.rejected",
                content="",
                content_hash=content_hash,
                provenance=provenance,
                session_id=session_id,
                tainted=tainted or bool(findings),
                injection_findings=findings,
                status="rejected",
                receipt_id=response.receipt_id,
            )

        # raw-free storage. Secrets are ALWAYS stripped from any persisted
        # text. A poisoned candidate (tainted or injection-bearing) can NEVER
        # be promoted, so its raw body has no use and only blast radius — it
        # keeps a hash + a redacted preview, not the content.
        poisoned = tainted or bool(findings)
        redacted = redact_secret_spans(content)
        candidate = MemoryCandidate(
            candidate_id="mem.{0:06d}".format(self.store.next_counter("memory_candidate_seq")),
            content="" if poisoned else redacted,
            content_hash=content_hash,
            preview=redacted[:120] if poisoned else "",
            provenance=provenance,
            session_id=session_id,
            tainted=poisoned,
            injection_findings=findings,
            status="candidate",
            receipt_id=response.receipt_id,
        )
        self.store.kv_set(_KV_PREFIX + candidate.candidate_id, candidate.model_dump_json())
        return candidate

    # --------------------------------------------------------------- promotion
    def promote(self, candidate_id: str, *, principal_id: str = "operator.local") -> dict[str, JsonValue]:
        candidate = self.get(candidate_id)
        if candidate is None:
            return {"promoted": False, "reason": "unknown_candidate"}
        if candidate.tainted:
            # poisoned memory can NEVER be promoted — re-author it from a
            # clean session instead; the refusal is evidence.
            event = self.engine.recorder.record_decision(
                run_id="run.memory.gate",
                payload={
                    "capability_id": "memory.promote",
                    "target": candidate_id,
                    "decision": TrustDecision.DENY.value,
                    "reason": "poisoned_candidate_blocked",
                    "principal_id": principal_id,
                },
            )
            return {
                "promoted": False,
                "reason": "poisoned_candidate_blocked",
                "receipt_id": event.record_id,
            }
        updated = candidate.model_copy(update={"status": "promoted"})
        self.store.kv_set(_KV_PREFIX + candidate_id, updated.model_dump_json())
        event = self.engine.recorder.record_decision(
            run_id="run.memory.gate",
            payload={
                "capability_id": "memory.promote",
                "target": candidate_id,
                "decision": "allow",
                "reason": "operator_review",
                "content_hash": candidate.content_hash,
                "principal_id": principal_id,
            },
        )
        return {"promoted": True, "receipt_id": event.record_id}

    # ------------------------------------------------------------------- reads
    def get(self, candidate_id: str) -> Optional[MemoryCandidate]:
        raw = self.store.kv_get(_KV_PREFIX + candidate_id)
        if raw is None:
            return None
        try:
            return MemoryCandidate.model_validate_json(raw)
        except ValueError:
            return None

    def promoted_memory(self) -> tuple[MemoryCandidate, ...]:
        """What a host may actually load as long-term memory."""
        promoted: list[MemoryCandidate] = []
        index = 1
        while True:
            candidate = self.get("mem.{0:06d}".format(index))
            if candidate is None:
                break
            if candidate.status == "promoted":
                promoted.append(candidate)
            index += 1
        return tuple(promoted)
