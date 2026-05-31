"""Context compaction helpers."""

from __future__ import annotations

from pathlib import Path

from zeus_agent.core.mneme import list_evidence
from zeus_agent.storage.run_store import RunStore


def compact_text(text: str, *, max_chars: int = 4000) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    head = cleaned[: max_chars // 2]
    tail = cleaned[-max_chars // 2 :]
    return f"{head}\n[... Zeus compacted {len(cleaned) - max_chars} chars ...]\n{tail}"


def build_run_context(run_id: str, *, home: Path | None = None, max_evidence: int = 20) -> dict[str, object]:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    evidence = list_evidence(run_id, home=home)[-max_evidence:]
    return {
        "run_id": run_id,
        "goal": contract.normalized_goal,
        "approval_state": contract.approval_state,
        "execution_status": spec.status,
        "acceptance_criteria": contract.acceptance_criteria,
        "tools_required": spec.tools_required,
        "recent_evidence": evidence,
    }

